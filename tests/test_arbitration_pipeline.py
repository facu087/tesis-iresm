"""
Tests de la integración del Árbitro en el pipeline y en el reporte exportado.

Cubre el adaptador desde el reporte del debate, el orden del router y cómo el
consenso llega al `StructuredReport`. Sin red ni LLM.

Caso de prueba base: neuropatía axonal sensitivomotora, paciente masculino de 42 años.
"""

import pytest

from backend.models.arbitration import (
    ArbitrationResult,
    ArbitrationStatus,
    ArbitrationSummary,
    ConsensusHypothesis,
    Contradiction,
    RecitationOutcome,
)
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import (
    AgentOutput,
    Critique,
    DebateRound,
    Report,
    RetrievedArticleRef,
)
from backend.pipeline.consensus import build_arbitration_input
from backend.pipeline.report_builder import build_export
from backend.pipeline.verification import SourceStatus, SourceVerification

ATTR = "Amiloidosis ATTR hereditaria como causa de la neuropatía axonal"
ATTR_OTRA = "Neuropatía axonal secundaria a amiloidosis por transtiretina"
B12 = "Déficit de vitamina B12 inducido por metformina"


def _h(text: str, pmids: list[str] | None = None) -> Hypothesis:
    return Hypothesis(
        text=text, priority=Priority.HIGH, evidence_level=EvidenceLevel.II,
        rationale="Fundamento de prueba.",
        sources=[Source(pmid=p, title=f"Artículo {p}") for p in (pmids or [])],
    )


def _report() -> Report:
    """Reporte como el que deja `debate.run_debate()` sobre el caso base."""
    r1 = [
        AgentOutput(agent_id="01", agent_name="Analista de Literatura",
                    hypotheses=[_h(ATTR, ["111"])]),
        AgentOutput(agent_id="03", agent_name="Consultor Clínico",
                    hypotheses=[_h(B12, ["333"])]),
    ]
    critica = Critique(
        from_agent_id="03", from_agent_name="Consultor Clínico",
        target_agent_id="01", target_hypothesis=ATTR,
        critique_text="Sin biopsia no se sostiene.", severity="HIGH",
    )
    r4 = [
        AgentOutput(agent_id="01", agent_name="Analista de Literatura",
                    hypotheses=[_h(ATTR, ["111"]), _h(ATTR_OTRA, ["222"])]),
        AgentOutput(agent_id="03", agent_name="Consultor Clínico",
                    hypotheses=[_h(B12, ["333"])]),
    ]
    finales = [h for o in r4 for h in o.hypotheses]
    return Report(
        case_summary="Varón de 42 años con neuropatía axonal sensitivomotora.",
        hypotheses=finales,
        agent_outputs=r1,
        debate_rounds=[
            DebateRound(round_number=2, critiques=[critica]),
            DebateRound(round_number=4, agent_outputs=r4),
        ],
        divergences=["divergencia vieja del debate"],
        retrieved_articles=[RetrievedArticleRef(pmid="999", title="Artículo recuperado")],
    )


def _case() -> ClinicalCase:
    return ClinicalCase(
        raw_text="[texto clínico anonimizado]",
        pico=PICOSynthesis(
            patient_profile="Masculino, 42 años",
            chief_complaint="Neuropatía axonal sensitivomotora progresiva",
            relevant_history=["Diabetes mellitus tipo 2"],
            negative_findings=["Panel CMT negativo"],
            disease_duration="18 meses",
            current_treatments=["pregabalina 150 mg/día"],
            procedures_done=["EMG"],
            comparison="Neuropatía diabética vs. amiloidosis hereditaria",
            primary_outcome="Etiología de la neuropatía axonal",
            secondary_outcomes=["respuesta a tratamiento"],
            biomarkers=["HbA1c 8.2%"],
            genetic_findings=["Panel CMT negativo"],
            clinical_narrative="Paciente masculino 42 años con neuropatía axonal.",
        ),
    )


# ── 8.3 Adaptador desde el reporte del debate ─────────────────────────────────

class TestBuildArbitrationInput:

    def test_toma_las_hipotesis_del_reporte(self):
        entrada = build_arbitration_input(_report())
        assert [h.text for h in entrada.hypotheses] == [ATTR, ATTR_OTRA, B12]

    def test_atribuye_cada_hipotesis_a_su_agente(self):
        entrada = build_arbitration_input(_report())
        assert entrada.hypothesis_agents == ["01", "01", "03"]

    def test_recoge_las_criticas_del_debate(self):
        entrada = build_arbitration_input(_report())
        assert len(entrada.critiques) == 1
        assert entrada.critiques[0].severity == "HIGH"

    def test_guarda_las_rondas_por_agente(self):
        entrada = build_arbitration_input(_report())
        assert [h.text for h in entrada.round_1_by_agent["01"]] == [ATTR]
        assert [h.text for h in entrada.final_by_agent["01"]] == [ATTR, ATTR_OTRA]

    def test_propaga_los_articulos_recuperados(self):
        entrada = build_arbitration_input(_report())
        assert [a.pmid for a in entrada.retrieved_articles] == ["999"]

    def test_nombres_de_agente(self):
        entrada = build_arbitration_input(_report())
        assert entrada.name_of("01") == "Analista de Literatura"

    def test_reporte_sin_debate_usa_la_ronda_1(self):
        """Con un solo agente no hay debate, pero el Árbitro igual arbitra."""
        salida = AgentOutput(agent_id="01", agent_name="Analista de Literatura",
                             hypotheses=[_h(ATTR)])
        report = Report(case_summary="…", hypotheses=[_h(ATTR)], agent_outputs=[salida])

        entrada = build_arbitration_input(report)

        assert entrada.hypothesis_agents == ["01"]

    def test_reporte_vacio_no_rompe(self):
        entrada = build_arbitration_input(Report(case_summary="…"))
        assert entrada.hypotheses == []
        assert entrada.hypothesis_agents == []


# ── 9.2 y 9.3 El consenso en el reporte exportado ─────────────────────────────

def _arbitraje() -> ArbitrationResult:
    consenso = [
        ConsensusHypothesis(
            hypothesis=_h(ATTR, ["111", "222"]),
            grouped=[_h(ATTR, ["111"]), _h(ATTR_OTRA, ["222"])],
            supporting_agents=["Analista de Literatura", "Especialista Genómica"],
            refuting_agents=["Consultor Clínico"],
            contradictions=[Contradiction(
                from_agent_id="03", from_agent_name="Consultor Clínico",
                severity="HIGH", critique_text="Sin biopsia no se sostiene.",
                target_hypothesis=ATTR,
            )],
            verdict="Sostenida por dos agentes, con una objeción abierta.",
            recitation=RecitationOutcome.MEJORADA,
        ),
        ConsensusHypothesis(
            hypothesis=_h(B12, ["333"]),
            grouped=[_h(B12, ["333"])],
            supporting_agents=["Consultor Clínico"],
        ),
    ]
    return ArbitrationResult(
        consensus=consenso,
        summary=ArbitrationSummary(
            status=ArbitrationStatus.OK,
            input_hypotheses=3, consensus_hypotheses=2, contradictions=1,
            cited_sources=3, rag_overlap=0, retrieved_articles=1,
        ),
    )


def _export(arbitration=None):
    return build_export(
        case=_case(), report=_report(), trials=[], processing_time=1.0,
        verifications={}, arbitration=arbitration,
    )


class TestReporteConConsenso:

    def test_las_hipotesis_del_reporte_son_las_de_consenso(self):
        reporte = _export(_arbitraje())
        assert len(reporte.hypotheses) == 2

    def test_respaldo_multiple(self):
        reporte = _export(_arbitraje())
        attr = next(h for h in reporte.hypotheses if h.text == ATTR)
        assert attr.supporting_agents == ["Analista de Literatura", "Especialista Genómica"]

    def test_refutacion_y_contradicciones(self):
        reporte = _export(_arbitraje())
        attr = next(h for h in reporte.hypotheses if h.text == ATTR)
        assert attr.refuting_agents == ["Consultor Clínico"]
        assert attr.contradictions[0].critique_text == "Sin biopsia no se sostiene."
        assert attr.contradictions[0].severity == "HIGH"

    def test_veredicto_del_arbitro(self):
        reporte = _export(_arbitraje())
        attr = next(h for h in reporte.hypotheses if h.text == ATTR)
        assert attr.arbiter_note.startswith("Sostenida por dos agentes")

    def test_marca_de_recitada(self):
        reporte = _export(_arbitraje())
        attr = next(h for h in reporte.hypotheses if h.text == ATTR)
        assert attr.recitation == "mejorada"

    def test_resumen_de_arbitraje(self):
        reporte = _export(_arbitraje())
        assert reporte.arbitration is not None
        assert reporte.arbitration.input_hypotheses == 3
        assert reporte.arbitration.consensus_hypotheses == 2
        assert reporte.arbitration.rag_overlap == 0
        assert reporte.arbitration.cited_sources == 3

    def test_las_divergencias_salen_del_arbitro(self):
        reporte = _export(_arbitraje())
        assert any("Consultor Clínico objetó" in d for d in reporte.debate_summary.divergences)
        assert reporte.debate_summary.consensus_reached is False

    def test_conteos_consistentes(self):
        """Spec: consenso ≤ entrada, mejoradas ≤ recitadas."""
        reporte = _export(_arbitraje())
        a = reporte.arbitration
        assert a.consensus_hypotheses <= a.input_hypotheses
        assert a.recitation.improved <= max(a.recitation.recited, a.recitation.improved)


class TestReporteSinArbitraje:
    """Contrato aditivo: sin Árbitro el reporte se arma exactamente como antes."""

    def test_arbitration_queda_nulo(self):
        assert _export().arbitration is None

    def test_las_hipotesis_son_las_del_debate(self):
        assert len(_export().hypotheses) == 3

    def test_los_campos_nuevos_tienen_default(self):
        h = _export().hypotheses[0]
        assert h.refuting_agents == []
        assert h.contradictions == []
        assert h.arbiter_note == ""
        assert h.recitation == "no_aplica"

    def test_las_divergencias_son_las_del_debate(self):
        assert _export().debate_summary.divergences == ["divergencia vieja del debate"]

    def test_el_json_sigue_validando(self):
        """Un cliente anterior al Árbitro lee el reporte sin enterarse."""
        datos = _export().model_dump()
        assert datos["arbitration"] is None
        assert "hypotheses" in datos and "bibliography" in datos


class TestArbitrajeDegradado:

    def test_consenso_degradado_conserva_todas(self):
        degradado = ArbitrationResult(
            consensus=[
                ConsensusHypothesis(hypothesis=_h(t), grouped=[_h(t)],
                                    supporting_agents=["Analista de Literatura"])
                for t in (ATTR, ATTR_OTRA, B12)
            ],
            summary=ArbitrationSummary(
                status=ArbitrationStatus.DEGRADADO,
                input_hypotheses=3, consensus_hypotheses=3,
            ),
        )
        reporte = _export(degradado)

        assert len(reporte.hypotheses) == 3
        assert reporte.arbitration.status == "degradado"
