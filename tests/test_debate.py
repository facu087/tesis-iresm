"""
Tests del motor de debate adversarial (backend/pipeline/debate.py)
y los métodos de debate de BaseAgent.

Tests unitarios: no llaman APIs externas.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.base_agent import _format_critiques, _format_output, _format_outputs
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import AgentOutput, Critique, DebateRound, Report
from backend.pipeline.debate import _critiques_for, _detect_divergences, run_debate


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _hypothesis(text: str, priority=Priority.HIGH, level=EvidenceLevel.II) -> Hypothesis:
    return Hypothesis(text=text, priority=priority, evidence_level=level, rationale="r")


def _output(agent_id: str, agent_name: str, texts: list[str]) -> AgentOutput:
    return AgentOutput(
        agent_id=agent_id,
        agent_name=agent_name,
        hypotheses=[_hypothesis(t) for t in texts],
        raw_response="{}",
    )


def _critique(from_id: str, from_name: str, target_id: str, target_hyp: str, severity: str = "HIGH") -> Critique:
    return Critique(
        from_agent_id=from_id,
        from_agent_name=from_name,
        target_agent_id=target_id,
        target_hypothesis=target_hyp,
        critique_text="Crítica de prueba",
        severity=severity,
    )


def _make_pico() -> PICOSynthesis:
    return PICOSynthesis(
        patient_profile="Masculino 42 años",
        chief_complaint="Neuropatía axonal",
        relevant_history=[],
        negative_findings=["Panel CMT negativo"],
        disease_duration="18 meses",
        current_treatments=[],
        procedures_done=["EMG"],
        comparison="No aplica",
        primary_outcome="Identificar etiología",
        secondary_outcomes=[],
        biomarkers=[],
        genetic_findings=[],
        clinical_narrative="Narrativa clínica de prueba.",
    )


# ── Tests: helpers de debate ───────────────────────────────────────────────────

class TestHelpers:
    def test_critiques_for_filtra_por_target(self):
        critiques = [
            _critique("01", "Agente 01", "03", "H1"),
            _critique("03", "Agente 03", "01", "H2"),
            _critique("01", "Agente 01", "03", "H3"),
        ]
        result = _critiques_for("03", critiques)
        assert len(result) == 2
        assert all(c.target_agent_id == "03" for c in result)

    def test_critiques_for_sin_resultados(self):
        critiques = [_critique("01", "A01", "03", "H1")]
        assert _critiques_for("02", critiques) == []

    def test_detect_divergences_hipotesis_mantenida(self):
        critiques = [_critique("01", "A01", "03", "neuropatía hereditaria no detectada", "HIGH")]
        final = [_output("03", "A03", ["neuropatía hereditaria no detectada por panel CMT"])]
        divs = _detect_divergences(critiques, final)
        assert len(divs) == 1
        assert "03" in divs[0]

    def test_detect_divergences_hipotesis_cambiada(self):
        critiques = [_critique("01", "A01", "03", "neuropatía hereditaria rara", "HIGH")]
        final = [_output("03", "A03", ["causa autoinmune completamente diferente sin relación"])]
        divs = _detect_divergences(critiques, final)
        assert len(divs) == 0

    def test_detect_divergences_ignora_severity_baja(self):
        critiques = [_critique("01", "A01", "03", "neuropatía hereditaria", "LOW")]
        final = [_output("03", "A03", ["neuropatía hereditaria confirmada"])]
        divs = _detect_divergences(critiques, final)
        assert len(divs) == 0


# ── Tests: BaseAgent.critique y revise ────────────────────────────────────────

class TestBaseAgentDebateMethods:
    def _make_agent(self):
        from backend.agents.agent_01_literature import LiteratureAnalystAgent
        return LiteratureAnalystAgent()

    def test_critique_parsea_json_correcto(self):
        agent = self._make_agent()
        mock_json = '''{
            "critiques": [
                {
                    "target_agent_id": "03",
                    "target_hypothesis": "hipótesis X",
                    "critique_text": "la evidencia es insuficiente",
                    "severity": "HIGH",
                    "alternative": "hipótesis alternativa Y"
                }
            ]
        }'''
        with patch.object(agent, "_call_llm", return_value=mock_json):
            own = _output("01", "A01", ["mi hipótesis"])
            others = [_output("03", "A03", ["hipótesis X"])]
            critiques = agent.critique("contexto", own, others)

        assert len(critiques) == 1
        assert critiques[0].from_agent_id == "01"
        assert critiques[0].target_agent_id == "03"
        assert critiques[0].severity == "HIGH"
        assert critiques[0].alternative == "hipótesis alternativa Y"

    def test_critique_severity_invalida_se_normaliza(self):
        agent = self._make_agent()
        mock_json = '{"critiques": [{"target_agent_id": "03", "target_hypothesis": "H", "critique_text": "C", "severity": "INVALID"}]}'
        with patch.object(agent, "_call_llm", return_value=mock_json):
            critiques = agent.critique("ctx", _output("01", "A01", []), [_output("03", "A03", ["H"])])
        assert critiques[0].severity == "MEDIUM"

    def test_critique_sin_resultados_devuelve_lista_vacia(self):
        agent = self._make_agent()
        with patch.object(agent, "_call_llm", return_value='{"critiques": []}'):
            critiques = agent.critique("ctx", _output("01", "A01", []), [])
        assert critiques == []

    def test_revise_devuelve_agent_output(self):
        agent = self._make_agent()
        mock_json = '''{
            "hypotheses": [{
                "text": "hipótesis revisada",
                "priority": "HIGH",
                "evidence_level": "II",
                "rationale": "respuesta a la crítica",
                "sources": []
            }]
        }'''
        with patch.object(agent, "_call_llm", return_value=mock_json):
            own = _output("01", "A01", ["hipótesis original"])
            critiques = [_critique("03", "A03", "01", "hipótesis original")]
            result = agent.revise("contexto", own, critiques)

        assert result.agent_id == "01"
        assert len(result.hypotheses) == 1
        assert result.hypotheses[0].text == "hipótesis revisada"


# ── Tests: run_debate ──────────────────────────────────────────────────────────

class TestRunDebate:
    def _make_round1_report(self) -> Report:
        return Report(
            case_summary="Narrativa de prueba.",
            agent_outputs=[
                _output("01", "Analista de Literatura", ["hipótesis literatura A"]),
                _output("03", "Consultor Clínico", ["hipótesis clínica B"]),
            ],
        )

    def _mock_agents(self, mock_a01_cls, mock_a03_cls):
        a01 = MagicMock()
        a01.AGENT_ID = "01"
        a01.AGENT_NAME = "Analista de Literatura"
        a01.critique.return_value = [_critique("01", "A01", "03", "hipótesis clínica B", "MEDIUM")]
        a01.revise.return_value = _output("01", "A01", ["hipótesis literatura revisada"])
        mock_a01_cls.return_value = a01

        a03 = MagicMock()
        a03.AGENT_ID = "03"
        a03.AGENT_NAME = "Consultor Clínico"
        a03.critique.return_value = [_critique("03", "A03", "01", "hipótesis literatura A", "LOW")]
        a03.revise.return_value = _output("03", "A03", ["hipótesis clínica revisada"])
        mock_a03_cls.return_value = a03

        return a01, a03

    def test_run_debate_produce_report_con_3_rondas(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        r1 = self._make_round1_report()

        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_agents(M01, M03)
            report = asyncio.run(run_debate(case, r1))

        assert len(report.debate_rounds) == 3
        assert report.debate_rounds[0].round_number == 2
        assert report.debate_rounds[1].round_number == 3
        assert report.debate_rounds[2].round_number == 4

    def test_run_debate_preserva_agent_outputs_ronda1(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        r1 = self._make_round1_report()

        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_agents(M01, M03)
            report = asyncio.run(run_debate(case, r1))

        assert len(report.agent_outputs) == 2

    def test_run_debate_hipotesis_finales_son_de_ronda4(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        r1 = self._make_round1_report()

        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_agents(M01, M03)
            report = asyncio.run(run_debate(case, r1))

        texts = [h.text for h in report.hypotheses]
        assert "hipótesis literatura revisada" in texts
        assert "hipótesis clínica revisada" in texts

    def test_run_debate_falla_sin_pico(self):
        case = ClinicalCase(raw_text="texto")
        r1 = self._make_round1_report()
        with pytest.raises(ValueError, match="case.pico es None"):
            asyncio.run(run_debate(case, r1))

    def test_run_debate_falla_sin_agent_outputs(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        r1 = Report(case_summary="s")
        with pytest.raises(ValueError, match="agent_outputs"):
            asyncio.run(run_debate(case, r1))

    def test_ronda2_critiques_almacenadas(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        r1 = self._make_round1_report()

        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_agents(M01, M03)
            report = asyncio.run(run_debate(case, r1))

        ronda2 = report.debate_rounds[0]
        assert ronda2.round_number == 2
        assert len(ronda2.critiques) == 2  # una de cada agente
