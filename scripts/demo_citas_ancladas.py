"""
Demo — Citas ancladas a la literatura del RAG (tarjeta #92, Sprint 5).

En la validación end-to-end de la tarjeta #58, de 25 PMIDs citados por los
agentes 23 existían en PubMed pero eran otro artículo, y ninguno salió de los
artículos que el RAG les ofreció: citaban de memoria. Ahora una cita con PMID
solo vale si ese PMID lo ofreció el RAG. El filtro corre al cerrar el debate
(después de la Ronda 4 y antes de la verificación), las fuentes sin PMID se
conservan y el reporte informa cuántas citas se descartaron.

Este script corre sin red ni cuota. Sobre el caso base (neuropatía axonal
sensitivomotora, varón de 42 años) arma un debate con los agentes reemplazados
por respuestas fijas y muestra entrada → salida en dos escenarios:

  con literatura: el RAG ofreció 5 artículos; las hipótesis citan PMIDs de
                  memoria, PMIDs ofrecidos y una guía clínica sin PMID
  sin literatura: el RAG no ofreció nada (base local caída); las hipótesis
                  citan 12 PMIDs

  entrada: citas de cada hipótesis y artículos ofrecidos
  salida:  fuentes que quedan, descartadas por hipótesis, total en el resumen
           de verificación y el pedido de revisión con la lista de literatura

    python scripts/demo_citas_ancladas.py

Artefactos en output/demo_citas_ancladas/:
    resultado.txt  → la corrida completa
    resumen.json   → conteos por escenario y comprobaciones

Sale con código 1 si alguna comprobación falla.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(_RAIZ))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.agents.agent_01_literature import LiteratureAnalystAgent
from backend.agents.base_agent import REGLA_CITAS
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import AgentOutput, Critique, Report, RetrievedArticleRef
from backend.pipeline.debate import run_debate
from backend.pipeline.report_builder import build_export

_OUT_DIR = _RAIZ / "output" / "demo_citas_ancladas"
_SEP = "═" * 78
_lineas: list[str] = []


def _p(texto: str = "") -> None:
    """Imprime y guarda la línea para resultado.txt."""
    print(texto)
    _lineas.append(texto)


# ── Caso base ──────────────────────────────────────────────────────────────────

def _pico() -> PICOSynthesis:
    return PICOSynthesis(
        patient_profile="Masculino, 42 años",
        chief_complaint="Neuropatía axonal sensitivomotora progresiva",
        relevant_history=["Diabetes mellitus tipo 2"],
        negative_findings=["Panel CMT negativo"],
        disease_duration="18 meses",
        current_treatments=["pregabalina 150 mg/día"],
        procedures_done=["EMG"],
        comparison="Neuropatía diabética vs. amiloidosis hereditaria",
        primary_outcome="Etiología de la neuropatía axonal",
        secondary_outcomes=[],
        biomarkers=["HbA1c 8.2%"],
        genetic_findings=["Panel CMT negativo"],
        clinical_narrative="Varón de 42 años con neuropatía axonal sensitivomotora de 18 meses.",
    )


_OFRECIDOS = [
    RetrievedArticleRef(pmid="29972753", title="Inotersen treatment for patients with hereditary transthyretin amyloidosis", year="2018", excerpt="(resumen)"),
    RetrievedArticleRef(pmid="29972757", title="Patisiran, an RNAi therapeutic, for hereditary transthyretin amyloidosis", year="2018", excerpt="(resumen)"),
    RetrievedArticleRef(pmid="31434727", title="Diabetic neuropathy: a position statement", year="2017", excerpt="(resumen)"),
    RetrievedArticleRef(pmid="33547161", title="Chronic idiopathic axonal polyneuropathy", year="2021", excerpt="(resumen)"),
    RetrievedArticleRef(pmid="30530513", title="Vitamin B12 deficiency neuropathy", year="2019", excerpt="(resumen)"),
]


def _hyp(texto: str, fuentes: list[Source]) -> Hypothesis:
    return Hypothesis(text=texto, priority=Priority.HIGH, evidence_level=EvidenceLevel.II,
                      rationale="Fundamento de prueba.", sources=fuentes)


def _hipotesis_con_literatura() -> tuple[list[Hypothesis], list[Hypothesis]]:
    a01 = [
        _hyp("Amiloidosis hereditaria por transtiretina (ATTRv)", [
            Source(pmid="29972757", title="Patisiran for hereditary transthyretin amyloidosis"),
            Source(pmid="31234567", title="Cita de memoria sobre ATTR"),
            Source(pmid="29972757", title="Patisiran (repetida)"),
        ]),
        _hyp("Polineuropatía axonal idiopática crónica", [
            Source(pmid="27654321", title="Cita de memoria sobre CIAP"),
        ]),
    ]
    a03 = [
        _hyp("Neuropatía diabética", [
            Source(pmid="31434727", title="Diabetic neuropathy: a position statement"),
            Source(title="Guía ADA de neuropatía diabética 2017"),
        ]),
        _hyp("Déficit de vitamina B12", [
            Source(pmid="12345678", title="Cita de memoria sobre B12"),
            Source(pmid="23456789", title="Otra cita de memoria"),
        ]),
    ]
    return a01, a03


def _hipotesis_sin_literatura() -> tuple[list[Hypothesis], list[Hypothesis]]:
    pmids = [str(30000001 + i) for i in range(12)]
    a01 = [_hyp("Amiloidosis hereditaria por transtiretina (ATTRv)",
                [Source(pmid=p, title=f"Artículo {p}") for p in pmids[:6]])]
    a03 = [_hyp("Neuropatía diabética",
                [Source(pmid=p, title=f"Artículo {p}") for p in pmids[6:]])]
    return a01, a03


# ── Debate con agentes de respuesta fija ───────────────────────────────────────

def _agente(agent_id: str, nombre: str, finales: list[Hypothesis]) -> MagicMock:
    agente = MagicMock()
    agente.AGENT_ID = agent_id
    agente.AGENT_NAME = nombre
    objetivo = "03" if agent_id == "01" else "01"
    agente.critique.return_value = [Critique(
        from_agent_id=agent_id, from_agent_name=nombre, target_agent_id=objetivo,
        target_hypothesis="(hipótesis de Ronda 1)", critique_text="Crítica de prueba.",
        severity="MEDIUM",
    )]
    agente.revise.return_value = AgentOutput(agent_id=agent_id, agent_name=nombre, hypotheses=finales)
    return agente


def _correr(ofrecidos, finales_01, finales_03):
    case = ClinicalCase(raw_text="[texto clínico anonimizado]", pico=_pico())
    ronda_1 = Report(
        case_summary="Varón de 42 años con neuropatía axonal sensitivomotora.",
        agent_outputs=[
            AgentOutput(agent_id="01", agent_name="Analista de Literatura", hypotheses=[_hyp("(hipótesis de Ronda 1)", [])]),
            AgentOutput(agent_id="03", agent_name="Consultor Clínico", hypotheses=[_hyp("(hipótesis de Ronda 1)", [])]),
        ],
        retrieved_articles=ofrecidos,
    )
    a01 = _agente("01", "Analista de Literatura", finales_01)
    a03 = _agente("03", "Consultor Clínico", finales_03)
    with patch("backend.pipeline.debate.LiteratureAnalystAgent", return_value=a01), \
         patch("backend.pipeline.debate.GenomicsSpecialistAgent",
               return_value=MagicMock(AGENT_ID="02", AGENT_NAME="Especialista Genómica")), \
         patch("backend.pipeline.debate.ClinicalConsultantAgent", return_value=a03):
        report = asyncio.run(run_debate(case, ronda_1))
    contexto_revision = a01.revise.call_args.args[0]
    contexto_critica = a01.critique.call_args.args[0]
    return case, report, contexto_revision, contexto_critica


def _pedido_de_revision(contexto: str) -> str:
    """Arma el pedido real de BaseAgent.revise() sin llamar al modelo."""
    agente = LiteratureAnalystAgent()
    capturado: dict[str, str] = {}

    def _falso(prompt: str, *, task: str) -> str:
        capturado["prompt"] = prompt
        return ('{"hypotheses": [{"text": "h", "priority": "LOW", "evidence_level": "III", '
                '"rationale": "r", "sources": []}]}')

    with patch.object(agente, "_call_llm", side_effect=_falso):
        agente.revise(contexto, AgentOutput(agent_id="01", agent_name="x", hypotheses=[]), [])
    return capturado["prompt"]


def _fmt(fuente: Source) -> str:
    return f"PMID {fuente.pmid}" if fuente.pmid else f'sin PMID: "{fuente.title}"'


# ── Escenarios ─────────────────────────────────────────────────────────────────

def _escenario(nombre, ofrecidos, finales_01, finales_03, esperado_descartadas, fallas) -> dict:
    _p(_SEP)
    _p(f"ESCENARIO: {nombre}")
    _p(_SEP)
    _p("ENTRADA")
    _p(f"  Artículos que ofreció el RAG ({len(ofrecidos)}):")
    for a in ofrecidos:
        _p(f"    [PMID: {a.pmid}] {a.title} ({a.year})")
    if not ofrecidos:
        _p("    (ninguno: la base local no respondió)")
    entrada = finales_01 + finales_03
    _p("  Citas de cada hipótesis al cerrar la Ronda 4:")
    for h in entrada:
        _p(f"    · {h.text}")
        for s in h.sources:
            _p(f"        {_fmt(s)}")

    case, report, ctx_revision, ctx_critica = _correr(ofrecidos, finales_01, finales_03)
    exportado = build_export(case, report, trials=[], processing_time=0.0)

    _p("")
    _p("SALIDA")
    pmids_ofrecidos = {a.pmid for a in ofrecidos}
    sin_fuentes = (
        "(ninguna fuente: queda especulativa y entra en la Ronda 5)" if ofrecidos
        else "(ninguna fuente: queda especulativa; sin literatura no hay Ronda 5)"
    )
    por_hipotesis = []
    for antes, despues in zip(entrada, report.hypotheses):
        quedan = [_fmt(s) for s in despues.sources]
        descartadas = sum(1 for s in antes.sources if s.pmid and s.pmid not in pmids_ofrecidos)
        repetidas = sum(1 for s in antes.sources if s.pmid in pmids_ofrecidos) - sum(
            1 for s in despues.sources if s.pmid)
        por_hipotesis.append({"quedan": len(quedan), "descartadas": descartadas, "repetidas": repetidas})
        _p(f"    · {despues.text}")
        _p(f"        quedan: {', '.join(quedan) or sin_fuentes}")
        _p(f"        descartadas por no venir del RAG: {descartadas}"
           + (f"  ·  repetida unificada: {repetidas}" if repetidas else ""))
    _p(f"  Hipótesis en el reporte: {len(report.hypotheses)} de {len(entrada)} (ninguna se descarta)")
    _p(f"  Resumen de verificación → fuera_del_rag = {exportado.verification.fuera_del_rag}")
    bibliografia = [s.pmid for s in exportado.bibliography if s.pmid]
    _p(f"  Bibliografía del reporte: {', '.join(bibliografia) or '(sin PMIDs)'}")

    pedido = _pedido_de_revision(ctx_revision)
    inicio = pedido.index("LITERATURA CIENTÍFICA DISPONIBLE")
    _p("")
    _p("  Pedido de revisión (Rondas 3 y 4), fragmento con la literatura:")
    for linea in pedido[inicio:].splitlines():
        if not linea.strip() or linea.startswith("="):
            break
        _p(f"    | {linea}")
    _p("  Pedido de revisión, regla de citas:")
    _p(f"    | CITAS: {REGLA_CITAS}")
    _p("")

    # Comprobaciones
    citados = {s.pmid for h in exportado.hypotheses for s in h.sources if s.pmid}
    if sum(d["descartadas"] for d in por_hipotesis) != exportado.verification.fuera_del_rag:
        fallas.append(f"{nombre}: el detalle por hipótesis no suma el total del resumen")
    if exportado.verification.fuera_del_rag != esperado_descartadas:
        fallas.append(f"{nombre}: fuera_del_rag={exportado.verification.fuera_del_rag}, se esperaba {esperado_descartadas}")
    if not citados <= pmids_ofrecidos:
        fallas.append(f"{nombre}: quedaron PMIDs no ofrecidos en el reporte: {sorted(citados - pmids_ofrecidos)}")
    if not set(bibliografia) <= pmids_ofrecidos:
        fallas.append(f"{nombre}: la bibliografía trae PMIDs no ofrecidos")
    if len(report.hypotheses) != len(entrada):
        fallas.append(f"{nombre}: se perdieron hipótesis")
    sin_pmid_antes = sum(1 for h in entrada for s in h.sources if not s.pmid)
    sin_pmid_despues = sum(1 for h in report.hypotheses for s in h.sources if not s.pmid)
    if sin_pmid_antes != sin_pmid_despues:
        fallas.append(f"{nombre}: se perdieron fuentes sin PMID")
    if REGLA_CITAS not in " ".join(pedido.split()):
        fallas.append(f"{nombre}: el pedido de revisión no trae la regla de citas")
    if "LITERATURA CIENTÍFICA DISPONIBLE" in ctx_critica:
        fallas.append(f"{nombre}: la crítica de la Ronda 2 recibió la lista de literatura")
    if "(resumen)" in pedido:
        fallas.append(f"{nombre}: el pedido de revisión trae resúmenes")
    for a in ofrecidos:
        if f"[PMID: {a.pmid}]" not in pedido:
            fallas.append(f"{nombre}: el pedido de revisión no lista el PMID {a.pmid}")

    return {
        "articulos_ofrecidos": len(ofrecidos),
        "hipotesis": len(report.hypotheses),
        "por_hipotesis": por_hipotesis,
        "fuera_del_rag": exportado.verification.fuera_del_rag,
        "bibliografia": bibliografia,
    }


def main() -> int:
    """Corre los dos escenarios, guarda los artefactos y devuelve el código de salida."""
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    fallas: list[str] = []
    resumen = {
        "con_literatura": _escenario(
            "con literatura (5 artículos ofrecidos)", _OFRECIDOS,
            *_hipotesis_con_literatura(), esperado_descartadas=4, fallas=fallas,
        ),
        "sin_literatura": _escenario(
            "sin literatura (RAG caído, 12 PMIDs citados)", [],
            *_hipotesis_sin_literatura(), esperado_descartadas=12, fallas=fallas,
        ),
    }

    _p(_SEP)
    if fallas:
        _p(f"FALLARON {len(fallas)} COMPROBACIONES:")
        for falla in fallas:
            _p(f"  ✗ {falla}")
    else:
        _p("TODAS LAS COMPROBACIONES PASARON")
    _p(_SEP)

    (_OUT_DIR / "resultado.txt").write_text("\n".join(_lineas) + "\n", encoding="utf-8")
    (_OUT_DIR / "resumen.json").write_text(
        json.dumps({"escenarios": resumen, "fallas": fallas}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
