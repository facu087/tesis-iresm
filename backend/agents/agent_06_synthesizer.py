"""
Agente 06 — Sintetizador
Modelo: openai/gpt-oss-120b via Groq (arquitectura final: ver .claude/CLAUDE.md)
Rol: redactar un resumen ejecutivo en prosa (máximo 5 oraciones) para el médico
     responsable a partir del `StructuredReport` ya construido. No toma
     decisiones sobre los datos: no agrupa, no cambia niveles ni agrega fuentes.

No participa del debate adversarial: expone `synthesize()`, no `run()`.

Guarda anti-invención: el resumen se descarta entero si cita un PMID, un NCT o
un símbolo génico que no aparezca en el reporte recibido. Un PMID que figura en
el reporte pero que la verificación bibliográfica no confirmó (inexistente,
discordante o no verificado) cuenta igual que uno inventado: una referencia sin
respaldo nunca se presenta como respaldo.

Privacidad: los logs registran el tipo de excepción o el token infractor
(un identificador público), nunca el texto del resumen ni datos clínicos.
"""

from __future__ import annotations

import asyncio
import logging
import re

from ..api.schemas import StructuredReport
from ..models.report import AgentOutput
from ..pipeline.verification import SourceStatus
from .base_agent import GROQ_MAIN, BaseAgent

logger = logging.getLogger(__name__)

_PMID_RE = re.compile(r"\b(\d{7,8})\b")
_NCT_RE = re.compile(r"\b(NCT\d{8})\b")
_GENE_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,7})\b")

# Vocabulario del propio reporte que tiene forma de símbolo génico.
_REPORT_TERMS = frozenset({
    "I", "II", "III", "IV", "EBM", "PMID", "PMIDS", "NCT", "HIGH", "MEDIUM", "LOW",
    "NEXUS", "PICO", "ADN", "ARN", "DNA", "RNA", "IA",
    # Vocabulario genómico que no nombra un gen.
    "CNV", "SNV", "SNP", "VUS", "WES", "WGS", "NGS", "MLPA", "ACMG", "HGVS", "PCR",
})

_MAX_TRIALS_IN_CONTEXT = 5
_MAX_CONTEXT_CHARS = 6000


def _genes_in(text: str) -> set[str]:
    """Siglas con forma de símbolo génico, sin las siglas clínicas conocidas."""
    # Import diferido: biomarker_extractor importa agents.model_tasks, que carga
    # este paquete; importarlo arriba arma un ciclo si el extractor se carga primero.
    from ..ingestion.biomarker_extractor import _NON_GENE_TERMS

    return {m.group(1) for m in _GENE_RE.finditer(text)} - _NON_GENE_TERMS - _REPORT_TERMS


def _confirmed_pmids(report: StructuredReport) -> set[str]:
    """
    PMIDs que el resumen puede citar: los confirmados contra PubMed.

    Un PMID puede figurar en varias fuentes (hipótesis y bibliografía). Criterio
    conservador: solo es citable si TODAS sus apariciones en el reporte están
    confirmadas; si alguna aparece como inexistente, discordante o sin verificar,
    se excluye. Citar de más un PMID dudoso es el error caro (el médico lo lee
    como respaldo); descartar de más solo cuesta el resumen, que es opcional.
    """
    todas = [s for h in report.hypotheses for s in h.sources] + list(report.bibliography)
    confirmados = {s.pmid for s in todas
                   if s.pmid and s.verification_status == SourceStatus.VERIFICADA.value}
    refutados = {s.pmid for s in todas
                 if s.pmid and s.verification_status != SourceStatus.VERIFICADA.value}
    return confirmados - refutados


def _report_text(report: StructuredReport) -> str:
    """Todo el texto del reporte del que el resumen puede tomar siglas."""
    parts = [report.case_summary.narrative, report.case_summary.patient_profile,
             report.case_summary.chief_complaint]
    for h in report.hypotheses:
        parts += [h.text, h.rationale, h.arbiter_note]
    for t in report.clinical_trials:
        parts += [t.title, *t.conditions]
    return "\n".join(p for p in parts if p)


_MARCA_RECORTE = " [...]"


def _recortar(texto: str, tope: int) -> str:
    """Texto con a lo sumo `tope` caracteres; si se acorta, termina en la marca visible."""
    if len(texto) <= tope:
        return texto
    return f"{texto[:max(tope - len(_MARCA_RECORTE), 0)].rstrip()}{_MARCA_RECORTE}".lstrip()


def _armar(
    report: StructuredReport,
    citables: set[str],
    narrativa: str,
    fundamentos: list[str],
    notas: list[str],
) -> str:
    """Arma el texto del contexto con los textos libres ya recortados (o no)."""
    lines = [f"=== Caso ===\n{narrativa}\n", "=== Hipótesis priorizadas ==="]
    for h, fundamento, nota in zip(report.hypotheses, fundamentos, notas):
        confirmados = sorted({s.pmid for s in h.sources if s.pmid in citables})
        dudosas = sum(1 for s in h.sources if s.pmid not in citables)
        pmids = ", ".join(confirmados) or "ninguno"
        if dudosas:
            pmids += f"; {dudosas} referencia(s) no confirmada(s), no citar"
        lines.append(
            f"{h.rank}. [prioridad {h.priority} / EBM {h.evidence_level} / {h.status}] "
            f"{h.text} — {fundamento} (PMIDs confirmados: {pmids})"
        )
        if h.arbiter_note:
            lines.append(f"   Árbitro: {nota}")

    if report.clinical_trials:
        lines.append("\n=== Ensayos clínicos ===")
        for t in report.clinical_trials[:_MAX_TRIALS_IN_CONTEXT]:
            lines.append(f"- {t.nct_id} ({t.compatibility}): {t.title}")

    v = report.verification
    lines.append(
        "\n=== Verificación bibliográfica ===\n"
        f"Fuentes: {v.total_fuentes}, verificadas: {v.verificadas}, "
        f"discordantes: {v.discordantes}, inexistentes: {v.inexistentes}. "
        f"Hipótesis respaldadas: {v.hipotesis_respaldadas}, "
        f"pendientes: {v.hipotesis_pendientes}, especulativas: {v.hipotesis_especulativas}."
    )
    return "\n".join(lines)


def build_context(report: StructuredReport) -> str:
    """
    Serializa el reporte a texto plano para el prompt del Sintetizador.

    Si el texto completo entra en `_MAX_CONTEXT_CHARS` se devuelve tal cual. Si
    no, se acortan SOLO los textos libres largos: la narrativa del caso y, por
    hipótesis, el fundamento y la nota del Árbitro. Quedan siempre completos y
    en su lugar los ensayos, la verificación bibliográfica y, de cada hipótesis,
    su rango, prioridad, nivel EBM, estado, enunciado y los PMIDs confirmados
    (de los que depende la guarda anti-invención).

    Regla de recorte (determinista): con lo que sobra del límite una vez
    descontado lo obligatorio, se busca el mayor tope común `L` tal que, al
    cortar cada texto libre a `L` caracteres, el total entre. Los textos más
    cortos que `L` se conservan enteros, así que el recorte cae sobre los más
    largos. Cada texto cortado termina en " [...]" (la marca cuenta dentro de `L`).

    Caso patológico: si lo obligatorio más la marca de cada texto libre ya
    supera el límite, todos los textos libres quedan reducidos a la marca y el
    contexto excede `_MAX_CONTEXT_CHARS`: se prefiere un contexto largo pero
    completo en ensayos y verificación a uno que omita bloques.
    """
    citables = _confirmed_pmids(report)
    hs = report.hypotheses
    libres = [report.case_summary.narrative or ""]
    libres += [h.rationale or "" for h in hs]
    libres += [h.arbiter_note or "" for h in hs]

    def armar(tope: int | None) -> str:
        cortar = (lambda t: t) if tope is None else (lambda t: _recortar(t, tope))
        n = len(hs)
        return _armar(
            report, citables, cortar(libres[0]),
            [cortar(t) for t in libres[1:1 + n]], [cortar(t) for t in libres[1 + n:]],
        )

    completo = armar(None)
    if len(completo) <= _MAX_CONTEXT_CHARS:
        return completo

    piso = len(_MARCA_RECORTE)
    if len(armar(piso)) > _MAX_CONTEXT_CHARS:
        return armar(piso)  # caso patológico: ver docstring
    bajo, alto = piso, max(len(t) for t in libres)  # armar(bajo) entra; armar(alto) no
    while alto - bajo > 1:
        medio = (bajo + alto) // 2
        if len(armar(medio)) <= _MAX_CONTEXT_CHARS:
            bajo = medio
        else:
            alto = medio
    return armar(bajo)


def check_invention(text: str, report: StructuredReport) -> str | None:
    """
    Devuelve el primer PMID, NCT o gen del texto que no está en el reporte, o
    el primer PMID que está pero no fue confirmado por la verificación, o None
    si el texto es limpio.
    """
    known_pmids = _confirmed_pmids(report)
    for m in _PMID_RE.finditer(text):
        if m.group(1) not in known_pmids:
            return m.group(1)

    known_ncts = {t.nct_id for t in report.clinical_trials}
    for m in _NCT_RE.finditer(text):
        if m.group(1) not in known_ncts:
            return m.group(1)

    known_genes = _genes_in(_report_text(report)) | known_ncts
    for gene in sorted(_genes_in(text)):
        if gene not in known_genes:
            return gene
    return None


class SynthesizerAgent(BaseAgent):
    """Agente 06 — redacta el resumen ejecutivo del reporte."""

    AGENT_ID = "06"
    AGENT_NAME = "Sintetizador"
    MODEL = GROQ_MAIN
    SYSTEM_PROMPT = (
        "Sos el Sintetizador de NEXUS, un sistema de soporte investigativo clínico. "
        "Recibís el reporte completo de un análisis. Escribí UN párrafo en español, "
        "de no más de 5 oraciones, dirigido al médico responsable, que resuma las "
        "hipótesis principales, su nivel de evidencia y estado de verificación, y "
        "los ensayos clínicos relevantes. No introduzcas datos, PMIDs, números NCT "
        "ni genes que no estén en el reporte. Tampoco introduzcas siglas, abreviaturas "
        "ni símbolos de genes que no aparezcan tal cual en el reporte que recibís: "
        "escribí esos conceptos con palabras. Solo podés citar los PMIDs listados "
        "como confirmados; nunca cites una referencia marcada como no confirmada. No uses lenguaje diagnóstico "
        "definitivo: son hipótesis de investigación ('sugiere', 'es compatible con'). "
        "Devolvé solo el párrafo, sin títulos, listas ni markdown."
    )

    def run(self, clinical_context: str) -> AgentOutput:
        """No aplica: el Sintetizador no participa del debate."""
        raise NotImplementedError("SynthesizerAgent expone synthesize(), no run()")

    async def synthesize(self, structured_report: StructuredReport) -> str | None:
        """
        Resumen ejecutivo del reporte, o None si el LLM falla, responde vacío o
        la guarda anti-invención lo descarta. Nunca propaga excepciones.
        """
        prompt = f"Reporte a sintetizar:\n\n{build_context(structured_report)}"
        try:
            raw = await asyncio.to_thread(self._call_llm, prompt, task="agente06_sintesis")
        except Exception as exc:
            logger.warning("[Ag06] Falló la llamada al LLM (%s); sin resumen", type(exc).__name__)
            return None

        text = (raw or "").strip()
        if not text or text.startswith("{"):
            logger.warning("[Ag06] Respuesta vacía o no textual; sin resumen")
            return None

        offender = check_invention(text, structured_report)
        if offender is not None:
            logger.warning(
                "[Ag06] Resumen descartado: cita %s, ausente o no confirmado en el reporte",
                offender,
            )
            return None
        return text
