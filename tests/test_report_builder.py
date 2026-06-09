"""
Tests del builder de reporte estructurado (backend/pipeline/report_builder.py).
"""

from backend.api.schemas import StructuredReport
from backend.models.biomarkers import BiomarkerProfile
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import AgentOutput, Critique, DebateRound, Report
from backend.models.trial import ClinicalTrial
from backend.pipeline.report_builder import build_export


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _source(pmid: str = "11111111", title: str = "Estudio A") -> Source:
    return Source(pmid=pmid, title=title)


def _hypothesis(
    text: str = "Hipótesis de prueba.",
    priority: Priority = Priority.HIGH,
    evidence_level: EvidenceLevel = EvidenceLevel.II,
    sources: list[Source] | None = None,
) -> Hypothesis:
    return Hypothesis(
        text=text,
        priority=priority,
        evidence_level=evidence_level,
        rationale="Razonamiento de prueba.",
        sources=[_source()] if sources is None else sources,
    )


def _agent_output(agent_id: str = "01", hypotheses: list[Hypothesis] | None = None) -> AgentOutput:
    return AgentOutput(
        agent_id=agent_id,
        agent_name=f"Agente {agent_id}",
        hypotheses=hypotheses or [_hypothesis()],
    )


def _make_pico() -> PICOSynthesis:
    return PICOSynthesis(
        patient_profile="Varón, 42 años",
        chief_complaint="neuropatía axonal",
        relevant_history=["diabetes"],
        negative_findings=[],
        disease_duration="2 años",
        current_treatments=["pregabalina"],
        procedures_done=["EMG"],
        comparison="No aplica",
        primary_outcome="identificar causa tratable",
        secondary_outcomes=[],
        biomarkers=[],
        genetic_findings=[],
        clinical_narrative="Paciente varón de 42 años con neuropatía axonal.",
    )


def _make_case(with_pico: bool = True) -> ClinicalCase:
    case = ClinicalCase(raw_text="texto de prueba")
    if with_pico:
        case.pico = _make_pico()
    case.biomarkers = BiomarkerProfile(genes=["TTR"])
    return case


def _make_report(
    hypotheses: list[Hypothesis] | None = None,
    agent_outputs: list[AgentOutput] | None = None,
    debate_rounds: list[DebateRound] | None = None,
    divergences: list[str] | None = None,
) -> Report:
    h = hypotheses or [_hypothesis()]
    return Report(
        case_summary="Resumen del caso de prueba.",
        hypotheses=h,
        agent_outputs=agent_outputs or [_agent_output()],
        debate_rounds=debate_rounds or [],
        divergences=divergences or [],
        sources_summary={"I": 0, "II": 1, "III": 0},
    )


def _make_trial() -> ClinicalTrial:
    return ClinicalTrial(
        nct_id="NCT00000001",
        title="Ensayo de prueba",
        status="RECRUITING",
        brief_summary="Resumen del ensayo.",
        url="https://clinicaltrials.gov/study/NCT00000001",
    )


def _build(
    case: ClinicalCase | None = None,
    report: Report | None = None,
    trials: list[ClinicalTrial] | None = None,
    processing_time: float = 10.5,
) -> StructuredReport:
    return build_export(
        case=case or _make_case(),
        report=report or _make_report(),
        trials=[_make_trial()] if trials is None else trials,
        processing_time=processing_time,
    )


# ── Tests: estructura general ──────────────────────────────────────────────────

class TestBuildExportEstructura:
    def test_devuelve_structured_report(self):
        result = _build()
        assert isinstance(result, StructuredReport)

    def test_contiene_todas_las_secciones(self):
        result = _build()
        assert result.metadata is not None
        assert result.case_summary is not None
        assert result.hypotheses is not None
        assert result.debate_summary is not None
        assert result.clinical_trials is not None
        assert result.bibliography is not None


# ── Tests: metadata ────────────────────────────────────────────────────────────

class TestMetadata:
    def test_contiene_version(self):
        result = _build()
        assert result.metadata.nexus_version == "0.3.0"

    def test_contiene_disclaimer(self):
        result = _build()
        assert "NEXUS" in result.metadata.disclaimer
        assert "diagnóstico" in result.metadata.disclaimer.lower()

    def test_processing_time_redondeado(self):
        result = _build(processing_time=12.3456789)
        assert result.metadata.processing_time_seconds == 12.35

    def test_generated_at_es_datetime(self):
        from datetime import datetime
        result = _build()
        assert isinstance(result.metadata.generated_at, datetime)


# ── Tests: case_summary ────────────────────────────────────────────────────────

class TestCaseSummary:
    def test_usa_pico_si_disponible(self):
        result = _build(case=_make_case(with_pico=True))
        assert result.case_summary.chief_complaint == "neuropatía axonal"
        assert result.case_summary.patient_profile == "Varón, 42 años"
        assert "pregabalina" in result.case_summary.current_treatments

    def test_usa_narrative_si_no_hay_pico(self):
        result = _build(case=_make_case(with_pico=False))
        assert result.case_summary.narrative == "Resumen del caso de prueba."

    def test_narrative_del_pico(self):
        result = _build(case=_make_case(with_pico=True))
        assert "42 años" in result.case_summary.narrative


# ── Tests: hipótesis rankeadas ─────────────────────────────────────────────────

class TestHypotheses:
    def test_hipotesis_tienen_rank(self):
        result = _build()
        assert result.hypotheses[0].rank == 1

    def test_ranks_son_consecutivos(self):
        h1 = _hypothesis("H1", Priority.HIGH, EvidenceLevel.I)
        h2 = _hypothesis("H2", Priority.LOW, EvidenceLevel.III)
        result = _build(report=_make_report(hypotheses=[h1, h2]))
        ranks = [h.rank for h in result.hypotheses]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_ordena_por_prioridad(self):
        h_low = _hypothesis("H baja", Priority.LOW, EvidenceLevel.I)
        h_high = _hypothesis("H alta", Priority.HIGH, EvidenceLevel.I)
        result = _build(report=_make_report(hypotheses=[h_low, h_high]))
        assert result.hypotheses[0].text == "H alta"
        assert result.hypotheses[1].text == "H baja"

    def test_ordena_por_evidencia_dentro_de_misma_prioridad(self):
        h_iii = _hypothesis("H-III", Priority.HIGH, EvidenceLevel.III)
        h_i = _hypothesis("H-I", Priority.HIGH, EvidenceLevel.I)
        result = _build(report=_make_report(hypotheses=[h_iii, h_i]))
        assert result.hypotheses[0].evidence_level == "I"

    def test_supporting_agents_incluye_agentes_de_ronda_1(self):
        h = _hypothesis("Hipótesis compartida.")
        output_01 = AgentOutput(agent_id="01", agent_name="Agente 01", hypotheses=[h])
        output_03 = AgentOutput(agent_id="03", agent_name="Agente 03", hypotheses=[h])
        report = _make_report(hypotheses=[h], agent_outputs=[output_01, output_03])
        result = _build(report=report)
        agents = result.hypotheses[0].supporting_agents
        assert "Agente 01" in agents
        assert "Agente 03" in agents

    def test_hipotesis_sin_soporte_tiene_lista_vacia(self):
        h = _hypothesis("Hipótesis sin soporte.")
        report = _make_report(
            hypotheses=[h],
            agent_outputs=[_agent_output(hypotheses=[_hypothesis("Otra hipótesis.")])],
        )
        result = _build(report=report)
        assert result.hypotheses[0].supporting_agents == []


# ── Tests: debate_summary ──────────────────────────────────────────────────────

class TestDebateSummary:
    def test_rounds_completed_sin_debate(self):
        result = _build(report=_make_report(debate_rounds=[]))
        assert result.debate_summary.rounds_completed == 1  # solo Ronda 1

    def test_rounds_completed_con_debate(self):
        rounds = [
            DebateRound(round_number=2, critiques=[]),
            DebateRound(round_number=3),
            DebateRound(round_number=4),
        ]
        result = _build(report=_make_report(debate_rounds=rounds))
        assert result.debate_summary.rounds_completed == 4  # Ronda 1 + 3 rondas debate

    def test_total_critiques(self):
        critique = Critique(
            from_agent_id="01", from_agent_name="Agente 01",
            target_agent_id="03", target_hypothesis="hipótesis X",
            critique_text="Crítica de prueba.", severity="HIGH",
        )
        rounds = [DebateRound(round_number=2, critiques=[critique, critique])]
        result = _build(report=_make_report(debate_rounds=rounds))
        assert result.debate_summary.total_critiques == 2

    def test_consensus_reached_sin_divergencias_high(self):
        result = _build(report=_make_report(divergences=["MEDIUM divergencia menor"]))
        assert result.debate_summary.consensus_reached is True

    def test_no_consensus_con_divergencias_high(self):
        result = _build(report=_make_report(divergences=["Agente 01 mantuvo hipótesis criticada [HIGH]"]))
        assert result.debate_summary.consensus_reached is False

    def test_divergencias_se_propagan(self):
        divs = ["Divergencia A", "Divergencia B"]
        result = _build(report=_make_report(divergences=divs))
        assert result.debate_summary.divergences == divs


# ── Tests: clinical_trials ────────────────────────────────────────────────────

class TestClinicalTrials:
    def test_trials_se_propagan(self):
        trials = [_make_trial(), _make_trial()]
        result = _build(trials=trials)
        assert len(result.clinical_trials) == 2

    def test_sin_trials(self):
        result = _build(trials=[])
        assert result.clinical_trials == []


# ── Tests: bibliography ───────────────────────────────────────────────────────

class TestBibliography:
    def test_deduplica_por_pmid(self):
        source = _source(pmid="99999999")
        h1 = _hypothesis("H1", sources=[source])
        h2 = _hypothesis("H2", sources=[source])
        result = _build(report=_make_report(hypotheses=[h1, h2]))
        pmids = [s.pmid for s in result.bibliography]
        assert pmids.count("99999999") == 1

    def test_incluye_fuentes_de_todas_las_hipotesis(self):
        s1 = _source(pmid="11111111")
        s2 = _source(pmid="22222222")
        h1 = _hypothesis("H1", sources=[s1])
        h2 = _hypothesis("H2", sources=[s2])
        result = _build(report=_make_report(hypotheses=[h1, h2]))
        pmids = {s.pmid for s in result.bibliography}
        assert "11111111" in pmids
        assert "22222222" in pmids

    def test_sin_fuentes(self):
        h = _hypothesis("H sin fuentes", sources=[])
        result = _build(report=_make_report(hypotheses=[h]))
        assert result.bibliography == []
