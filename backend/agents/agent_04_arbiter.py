"""
Agente 04 — Árbitro Verificador.

Cierra el debate: agrupa las hipótesis equivalentes de los tres agentes en un
consenso, documenta las contradicciones que quedaron abiertas y emite un
veredicto por hipótesis apoyado en la verificación bibliográfica y el nivel de
evidencia efectivo.

No participa del debate ni genera hipótesis propias: arbitra sobre lo producido.

**Agente híbrido**, mismo criterio que el Agente 05. El LLM hace solo dos cosas
—proponer qué hipótesis son equivalentes y redactar los veredictos— y nunca
descarta una hipótesis, nunca introduce referencias y nunca altera un nivel de
evidencia. Todo lo que decide algo es determinista y vive en
`pipeline/consensus.py` y `pipeline/evidence.py`.

Las dos llamadas al LLM intercambian **índices**, nunca texto: el modelo se
refiere a las hipótesis por número, así que validarlo se reduce a chequear
enteros y no puede reescribir lo que un agente afirmó.
"""

from __future__ import annotations

import asyncio
import re
import sys
from collections.abc import Mapping, Sequence

from ..models.arbitration import (
    ArbitrationInput,
    ArbitrationResult,
    ArbitrationStatus,
    ConsensusHypothesis,
)
from ..models.report import AgentOutput
from ..pipeline import consensus as consensus_module
from ..pipeline.evidence import classify_hypothesis
from ..pipeline.verification import SourceVerification
from .base_agent import GROQ_MAIN, BaseAgent

# Un PMID es un entero de 1 a 8 dígitos; se buscan los de 5 o más para no
# confundirlos con años ni con números sueltos del texto.
_PMID_EN_TEXTO = re.compile(r"\b\d{5,8}\b")

# Cuánto del enunciado se le manda al modelo al agrupar. Los fundamentos
# completos no entran: con 12k TPM de cuota, el prompt de agrupación tiene que
# ser corto (design, Risks).
_MAX_TEXTO_PROMPT = 220
_MAX_VEREDICTO = 600


class ArbiterAgent(BaseAgent):
    """Agente 04 — Árbitro Verificador."""

    AGENT_ID = "04"
    AGENT_NAME = "Árbitro Verificador"
    MODEL = GROQ_MAIN
    SYSTEM_PROMPT = """Sos el árbitro de un panel de agentes de IA que analizó un caso
clínico complejo. Tu trabajo es ordenar lo que produjo el panel para que un médico pueda
leerlo, no agregar conclusiones propias.

Tenés dos tareas, según lo que te pidan en cada mensaje:
1. Agrupar las hipótesis que afirman lo mismo, aunque estén redactadas distinto.
2. Redactar, para cada hipótesis ya agrupada, un veredicto breve en español que explique
   en qué quedó después del debate y de la verificación bibliográfica.

REGLAS CRÍTICAS:
1. NO emitís diagnósticos. Son hipótesis de investigación para el médico responsable.
2. NUNCA descartes ni elimines una hipótesis. Si te parece débil, eso se refleja en el
   veredicto, no en su exclusión.
3. NUNCA inventes hipótesis: solo podés referirte a las que te envían, por su número.
4. NUNCA cites PMIDs, referencias ni artículos. El estado bibliográfico te lo dan hecho;
   tu veredicto lo describe en palabras, sin números de referencia.
5. NUNCA contradigas el estado ni el nivel de evidencia que te informan. Si te dicen que
   una hipótesis es especulativa, tu veredicto no puede presentarla como respaldada.
6. Agrupá solo lo que afirma lo mismo. Dos hipótesis sobre la misma enfermedad pero con
   mecanismos distintos son hipótesis distintas.
7. Respondé ÚNICAMENTE con un objeto JSON válido, sin texto adicional ni markdown."""

    # ── Interfaz del debate: este agente no participa ─────────────────

    def run(self, clinical_context: str) -> AgentOutput:
        """
        No implementado a propósito.

        El Árbitro no genera hipótesis ni debate con los demás: arbitra sobre
        las hipótesis que el debate ya produjo.
        """
        raise NotImplementedError(
            "El Agente 04 no participa del debate: usar arbitrate()"
        )

    # ── Punto de entrada ──────────────────────────────────────────────

    async def arbitrate(
        self,
        entrada: ArbitrationInput,
        verifications: Mapping[str, SourceVerification] | None = None,
    ) -> ArbitrationResult:
        """
        Consolida el resultado del debate en un consenso con veredictos.

        Nunca lanza por una falla del modelo: si la agrupación no se puede usar,
        devuelve el consenso degradado (cada hipótesis su propio grupo) y lo
        deja asentado en el resumen.

        Args:
            entrada:       Contrato neutral armado desde el Report del debate.
            verifications: Veredictos de `verify_report_sources()`. Vacío si la
                           verificación no pudo ejecutarse: las hipótesis quedan
                           pendientes y el consenso se arma igual.

        Returns:
            ArbitrationResult con el consenso y el resumen del arbitraje.
        """
        verifications = verifications or {}
        retrieved = list(entrada.retrieved_articles)

        if not entrada.hypotheses:
            return ArbitrationResult(
                summary=consensus_module.summarize(
                    [], entrada, retrieved, status=ArbitrationStatus.SIN_HIPOTESIS
                )
            )

        grupos, estado = await self._group(entrada)
        consenso = consensus_module.assemble(grupos, entrada, verifications)

        descartadas = 0
        if estado is ArbitrationStatus.OK:
            descartadas = await self._write_verdicts(consenso, entrada, verifications)

        return ArbitrationResult(
            consensus=consenso,
            summary=consensus_module.summarize(
                consenso, entrada, retrieved,
                status=estado,
                discarded_references=descartadas,
            ),
        )

    # ── 1. Agrupación (LLM) ───────────────────────────────────────────

    async def _group(
        self, entrada: ArbitrationInput
    ) -> tuple[list[list[int]], ArbitrationStatus]:
        """
        Propone qué hipótesis son equivalentes y valida la partición.

        Una sola llamada al LLM. Ante cualquier falla devuelve la partición
        trivial (una hipótesis por grupo) y estado degradado: el análisis
        continúa con el reporte sin consolidar, que es como se ve hoy.
        """
        total = len(entrada.hypotheses)
        try:
            raw = await asyncio.to_thread(self._call_llm, _build_grouping_prompt(entrada))
            datos = self.extract_json(raw)
        except Exception as exc:
            self._log_fallback("agrupación de hipótesis", exc)
            return [[i] for i in range(total)], ArbitrationStatus.DEGRADADO

        crudos = datos.get("groups")
        if not isinstance(crudos, list):
            self._log_fallback(
                "agrupación de hipótesis", ValueError("sin clave 'groups'")
            )
            return [[i] for i in range(total)], ArbitrationStatus.DEGRADADO

        # El modelo numera desde 1; adentro se trabaja con índices desde 0.
        propuestos: list[list[int]] = []
        for grupo in crudos:
            if not isinstance(grupo, list):
                continue
            propuestos.append([_as_index(x, total) for x in grupo])  # type: ignore[misc]

        return consensus_module.normalize_partition(
            [[i for i in grupo if i is not None] for grupo in propuestos], total
        ), ArbitrationStatus.OK

    # ── 2. Veredictos (LLM) ───────────────────────────────────────────

    async def _write_verdicts(
        self,
        consenso: Sequence[ConsensusHypothesis],
        entrada: ArbitrationInput,
        verifications: Mapping[str, SourceVerification],
    ) -> int:
        """
        Redacta el veredicto de cada hipótesis de consenso, con guardas.

        El estado bibliográfico y el nivel efectivo se le dan ya calculados: el
        modelo los describe, no los decide. Si el veredicto que devuelve cita un
        PMID —cosa que el prompt prohíbe— se descarta entero: no se le deja
        inyectar referencias al texto que lee el médico.

        Returns:
            Cuántos veredictos se descartaron por introducir referencias.
        """
        if not consenso:
            return 0

        try:
            prompt = _build_verdict_prompt(consenso, verifications)
            raw = await asyncio.to_thread(self._call_llm, prompt)
            datos = self.extract_json(raw)
        except Exception as exc:
            # Sin veredictos el consenso igual sirve: tiene respaldo, refutación
            # y contradicciones, que son datos, no redacción.
            self._log_fallback("redacción de veredictos", exc)
            return 0

        permitidos = _allowed_pmids(entrada)
        descartadas = 0

        for item in datos.get("verdicts", []):
            if not isinstance(item, dict):
                continue
            indice = _as_index(item.get("hypothesis"), len(consenso))
            if indice is None:
                continue
            texto = item.get("verdict")
            if not isinstance(texto, str) or not texto.strip():
                continue

            inventados = {p for p in _PMID_EN_TEXTO.findall(texto) if p not in permitidos}
            if inventados:
                descartadas += 1
                continue

            consenso[indice].verdict = texto.strip()[:_MAX_VEREDICTO]

        return descartadas

    # ── Logging ───────────────────────────────────────────────────────

    def _log_fallback(self, paso: str, exc: BaseException) -> None:
        """
        Registra un fallback con el tipo de excepción y nada más.

        Nunca `str(exc)`: `extract_json` mete la respuesta del LLM en el mensaje,
        y esa respuesta habla del caso clínico.
        """
        print(
            f"[NEXUS] Agente {self.AGENT_ID} — {paso}: fallback ({type(exc).__name__})",
            file=sys.stderr,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _as_index(valor: object, total: int) -> int | None:
    """Convierte el número 1-based que usa el LLM en un índice válido."""
    if isinstance(valor, bool):
        return None
    try:
        numero = int(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if 1 <= numero <= total:
        return numero - 1
    return None


def _allowed_pmids(entrada: ArbitrationInput) -> set[str]:
    """PMIDs que el Árbitro tiene permitido mencionar: los que ya estaban."""
    citados = consensus_module.cited_pmids(entrada.hypotheses)
    return citados | {a.pmid for a in entrada.retrieved_articles if a.pmid}


def _build_grouping_prompt(entrada: ArbitrationInput) -> str:
    """Arma el pedido de agrupación, con las hipótesis numeradas desde 1."""
    lineas = [
        "Estas son las hipótesis que produjo el panel al cerrar el debate. "
        "Varias pueden afirmar lo mismo con distinta redacción.",
        "",
    ]
    for numero, hypothesis in enumerate(entrada.hypotheses, 1):
        agente = entrada.name_of(entrada.agent_of(numero - 1))
        lineas.append(f"{numero}. [{agente}] {hypothesis.text[:_MAX_TEXTO_PROMPT]}")

    lineas += [
        "",
        "Agrupá las que afirman lo mismo. Cada hipótesis va en exactamente un grupo, "
        "y las que no se parecen a ninguna otra van solas en su propio grupo.",
        "No omitas ninguna. No agregues números que no estén en la lista.",
        "",
        "Respondé ÚNICAMENTE con JSON válido:",
        '{"groups": [[1, 3], [2], [4]]}',
    ]
    return "\n".join(lineas)


def _build_verdict_prompt(
    consenso: Sequence[ConsensusHypothesis],
    verifications: Mapping[str, SourceVerification],
) -> str:
    """
    Arma el pedido de veredictos con el estado y el nivel ya calculados.

    El modelo recibe el resultado de la clasificación determinista, no los datos
    para calcularla: así no tiene margen para llegar a otra conclusión.
    """
    lineas = [
        "Para cada hipótesis del consenso, redactá un veredicto breve (2 o 3 oraciones) "
        "que explique en qué quedó después del debate y de la verificación bibliográfica.",
        "",
        "El estado y el nivel de evidencia ya están calculados y NO se discuten: "
        "tu veredicto los explica en palabras.",
        "No menciones números de PMID ni de referencia.",
        "",
    ]
    for numero, item in enumerate(consenso, 1):
        evaluacion = classify_hypothesis(item.hypothesis, verifications)
        lineas.append(f"{numero}. {item.hypothesis.text[:_MAX_TEXTO_PROMPT]}")
        lineas.append(
            f"   estado: {evaluacion.status.value} · "
            f"nivel de evidencia efectivo: {evaluacion.effective_level.value} · "
            f"fuentes verificadas: {evaluacion.verified_sources}"
        )
        if item.supporting_agents:
            lineas.append(f"   la sostienen: {', '.join(item.supporting_agents)}")
        for contra in item.contradictions:
            lineas.append(
                f"   objeción de {contra.from_agent_name}: "
                f"{contra.critique_text[:_MAX_TEXTO_PROMPT]}"
            )

    lineas += [
        "",
        "Respondé ÚNICAMENTE con JSON válido:",
        '{"verdicts": [{"hypothesis": 1, "verdict": "…"}]}',
    ]
    return "\n".join(lineas)
