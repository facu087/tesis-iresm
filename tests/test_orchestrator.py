"""
Tests del orquestador (backend/pipeline/orchestrator.py).

Tests unitarios: mockean los agentes y pico.build() — no llaman APIs.
Tests de integración: marcados con @pytest.mark.integration, requieren GROQ_API_KEY.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority
from backend.models.report import AgentOutput, Report
from backend.pipeline.orchestrator import _build_sources_summary, run_round_1
from backend.models.hypothesis import Source


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_pico() -> PICOSynthesis:
    return PICOSynthesis(
        patient_profile="Masculino 42 años",
        chief_complaint="Neuropatía axonal progresiva",
        relevant_history=["Padre con problemas de equilibrio"],
        negative_findings=["Panel CMT 40 genes negativo", "Anticuerpos paraneoplásicos negativos"],
        disease_duration="18 meses",
        current_treatments=[],
        procedures_done=["EMG axonal difuso", "LCR normal"],
        comparison="No aplica",
        primary_outcome="Identificar etiología de neuropatía axonal con compromiso autonómico",
        secondary_outcomes=[],
        biomarkers=[],
        genetic_findings=[],
        clinical_narrative="Paciente masculino de 42 años con neuropatía axonal sensitivomotora "
                           "progresiva de 18 meses de evolución y compromiso autonómico.",
    )


def _make_agent_output(agent_id: str, agent_name: str, priority: Priority) -> AgentOutput:
    return AgentOutput(
        agent_id=agent_id,
        agent_name=agent_name,
        hypotheses=[
            Hypothesis(
                text=f"Hipótesis del agente {agent_id}",
                priority=priority,
                evidence_level=EvidenceLevel.II,
                rationale="Razonamiento de prueba",
                sources=[Source(pmid=f"1234567{agent_id}", title="Paper de prueba", year=2023)],
            )
        ],
        raw_response='{"hypotheses": []}',
    )


# ── Tests: _build_sources_summary ─────────────────────────────────────────────

class TestBuildSourcesSummary:
    def test_sin_hipotesis(self):
        result = _build_sources_summary([])
        assert result == {"I": 0, "II": 0, "III": 0}

    def test_cuenta_por_nivel(self):
        hypotheses = [
            Hypothesis(
                text="H1", priority=Priority.HIGH, evidence_level=EvidenceLevel.I,
                rationale="r",
                sources=[Source(pmid="111", title="P1", year=2020)],
            ),
            Hypothesis(
                text="H2", priority=Priority.MEDIUM, evidence_level=EvidenceLevel.II,
                rationale="r",
                sources=[Source(pmid="222", title="P2", year=2021)],
            ),
            Hypothesis(
                text="H3", priority=Priority.LOW, evidence_level=EvidenceLevel.III,
                rationale="r",
                sources=[],
            ),
        ]
        result = _build_sources_summary(hypotheses)
        assert result["I"] == 1
        assert result["II"] == 1
        assert result["III"] == 0  # sin fuentes

    def test_no_cuenta_pmids_duplicados(self):
        """La misma fuente citada en dos hipótesis se cuenta una sola vez."""
        h = Hypothesis(
            text="H", priority=Priority.HIGH, evidence_level=EvidenceLevel.II,
            rationale="r",
            sources=[Source(pmid="999", title="Mismo paper", year=2022)],
        )
        result = _build_sources_summary([h, h])
        assert result["II"] == 1


# ── Tests: run_round_1 ─────────────────────────────────────────────────────────

class TestRunRound1:
    def test_requiere_pico_completado(self):
        case = ClinicalCase(raw_text="texto")
        with pytest.raises(ValueError, match="case.pico es None"):
            asyncio.run(run_round_1(case))

    def test_combina_outputs_de_ambos_agentes(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        output_01 = _make_agent_output("01", "Analista de Literatura", Priority.HIGH)
        output_03 = _make_agent_output("03", "Consultor Clínico", Priority.MEDIUM)

        with patch("backend.pipeline.orchestrator.LiteratureAnalystAgent") as MockA01, \
             patch("backend.pipeline.orchestrator.ClinicalConsultantAgent") as MockA03:

            MockA01.return_value.AGENT_ID = "01"
            MockA01.return_value.AGENT_NAME = "Analista de Literatura"
            MockA01.return_value.run.return_value = output_01

            MockA03.return_value.AGENT_ID = "03"
            MockA03.return_value.AGENT_NAME = "Consultor Clínico"
            MockA03.return_value.run.return_value = output_03

            report = asyncio.run(run_round_1(case))

        assert len(report.agent_outputs) == 2
        assert len(report.hypotheses) == 2
        assert report.case_summary == case.pico.clinical_narrative

    def test_report_incluye_sources_summary(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        output_01 = _make_agent_output("01", "Analista de Literatura", Priority.HIGH)
        output_03 = _make_agent_output("03", "Consultor Clínico", Priority.MEDIUM)

        with patch("backend.pipeline.orchestrator.LiteratureAnalystAgent") as MockA01, \
             patch("backend.pipeline.orchestrator.ClinicalConsultantAgent") as MockA03:
            MockA01.return_value.AGENT_ID = "01"
            MockA01.return_value.AGENT_NAME = "Analista de Literatura"
            MockA01.return_value.run.return_value = output_01
            MockA03.return_value.AGENT_ID = "03"
            MockA03.return_value.AGENT_NAME = "Consultor Clínico"
            MockA03.return_value.run.return_value = output_03

            report = asyncio.run(run_round_1(case))

        assert "I" in report.sources_summary
        assert "II" in report.sources_summary
        assert "III" in report.sources_summary

    def test_un_agente_falla_el_otro_continua(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        output_03 = _make_agent_output("03", "Consultor Clínico", Priority.HIGH)

        with patch("backend.pipeline.orchestrator.LiteratureAnalystAgent") as MockA01, \
             patch("backend.pipeline.orchestrator.ClinicalConsultantAgent") as MockA03:
            MockA01.return_value.AGENT_ID = "01"
            MockA01.return_value.AGENT_NAME = "Analista de Literatura"
            MockA01.return_value.run.side_effect = RuntimeError("API caída")
            MockA03.return_value.AGENT_ID = "03"
            MockA03.return_value.AGENT_NAME = "Consultor Clínico"
            MockA03.return_value.run.return_value = output_03

            report = asyncio.run(run_round_1(case))

        assert len(report.agent_outputs) == 1
        assert report.agent_outputs[0].agent_id == "03"

    def test_todos_los_agentes_fallan_lanza_excepcion(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())

        with patch("backend.pipeline.orchestrator.LiteratureAnalystAgent") as MockA01, \
             patch("backend.pipeline.orchestrator.ClinicalConsultantAgent") as MockA03:
            MockA01.return_value.AGENT_ID = "01"
            MockA01.return_value.AGENT_NAME = "Analista de Literatura"
            MockA01.return_value.run.side_effect = RuntimeError("fallo")
            MockA03.return_value.AGENT_ID = "03"
            MockA03.return_value.AGENT_NAME = "Consultor Clínico"
            MockA03.return_value.run.side_effect = RuntimeError("fallo")

            with pytest.raises(RuntimeError, match="Todos los agentes fallaron"):
                asyncio.run(run_round_1(case))
