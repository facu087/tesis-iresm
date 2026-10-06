"""
Tests del motor de debate adversarial (backend/pipeline/debate.py)
y los métodos de debate de BaseAgent.

Tests unitarios: no llaman APIs externas.
"""

import asyncio
import json
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

    @pytest.mark.parametrize("declarado, esperado", [
        ("Agent 02", "02"),     # formas observadas en la corrida real del 2026-10-06
        ("Agent01", "01"),
        ("Agent03", "03"),
        ("Agente 3", "03"),
        ("ID:02", "02"),
        (" 03 ", "03"),
        (3, "03"),
    ])
    def test_critique_normaliza_el_id_del_destinatario(self, declarado, esperado):
        agent = self._make_agent()
        mock_json = json.dumps({"critiques": [{
            "target_agent_id": declarado, "target_hypothesis": "H",
            "critique_text": "C", "severity": "HIGH",
        }]})
        with patch.object(agent, "_call_llm", return_value=mock_json):
            criticados = [_output(i, f"A{i}", ["H"]) for i in ("01", "02", "03")]
            critiques = agent.critique("ctx", _output("04", "A04", []), criticados)
        assert critiques[0].target_agent_id == esperado

    def test_critique_con_destinatario_normalizado_llega_al_agente(self):
        agent = self._make_agent()
        mock_json = json.dumps({"critiques": [{
            "target_agent_id": "Agent 03", "target_hypothesis": "H",
            "critique_text": "C", "severity": "HIGH",
        }]})
        with patch.object(agent, "_call_llm", return_value=mock_json):
            critiques = agent.critique("ctx", _output("01", "A01", []), [_output("03", "A03", ["H"])])
        assert len(_critiques_for("03", critiques)) == 1

    @pytest.mark.parametrize("declarado", ["Consultor Clínico", "", None])
    def test_critique_sin_id_reconocible_no_se_atribuye_a_nadie(self, declarado):
        agent = self._make_agent()
        mock_json = json.dumps({"critiques": [{
            "target_agent_id": declarado, "target_hypothesis": "H",
            "critique_text": "C", "severity": "HIGH",
        }]})
        with patch.object(agent, "_call_llm", return_value=mock_json):
            critiques = agent.critique("ctx", _output("01", "A01", []), [_output("03", "A03", ["H"])])
        assert not any(_critiques_for(i, critiques) for i in ("01", "02", "03"))

    @pytest.mark.parametrize("declarado", [
        "hipótesis 2 del Agente 03",   # dos números: no se elige uno por posición
        "Agentes 01 y 03",
        "3.0",                         # dos corridas de dígitos
        3.0,                           # un float nunca es un ID
        "003",                         # tres dígitos
        "Agente ٣",                    # dígito Unicode no ASCII
        "Agente 03 ٢",
        True,
        -3,
    ])
    def test_critique_con_destinatario_ambiguo_queda_sin_atribuir(self, declarado):
        agent = self._make_agent()
        mock_json = json.dumps({"critiques": [{
            "target_agent_id": declarado, "target_hypothesis": "H",
            "critique_text": "C", "severity": "HIGH",
        }]})
        with patch.object(agent, "_call_llm", return_value=mock_json):
            critiques = agent.critique(
                "ctx", _output("01", "A01", []),
                [_output("02", "A02", ["H"]), _output("03", "A03", ["H"])],
            )
        assert critiques[0].target_agent_id == ""

    @pytest.mark.parametrize("declarado", ["Agent 04", "04", 4, "Agente 99"])
    def test_critique_a_un_agente_que_no_fue_criticado_queda_sin_atribuir(self, declarado):
        agent = self._make_agent()
        mock_json = json.dumps({"critiques": [{
            "target_agent_id": declarado, "target_hypothesis": "H",
            "critique_text": "C", "severity": "HIGH",
        }]})
        with patch.object(agent, "_call_llm", return_value=mock_json):
            critiques = agent.critique("ctx", _output("01", "A01", []), [_output("03", "A03", ["H"])])
        assert critiques[0].target_agent_id == ""

    def test_critique_dirigida_al_propio_autor_queda_sin_atribuir(self):
        agent = self._make_agent()
        mock_json = json.dumps({"critiques": [{
            "target_agent_id": "Agent 01", "target_hypothesis": "H",
            "critique_text": "C", "severity": "HIGH",
        }]})
        with patch.object(agent, "_call_llm", return_value=mock_json):
            critiques = agent.critique("ctx", _output("01", "A01", []), [_output("03", "A03", ["H"])])
        assert critiques[0].target_agent_id == ""

    def test_parse_critiques_con_un_solo_argumento_aplica_solo_la_regla_de_formato(self):
        agent = self._make_agent()
        raw = json.dumps({"critiques": [
            {"target_agent_id": "Agent 07", "target_hypothesis": "H", "critique_text": "C"},
            {"target_agent_id": "Agentes 01 y 03", "target_hypothesis": "H", "critique_text": "C"},
        ]})
        criticas = agent._parse_critiques(raw)
        assert [c.target_agent_id for c in criticas] == ["07", ""]

    def test_critique_pide_el_id_de_dos_digitos_en_el_prompt(self):
        agent = self._make_agent()
        with patch.object(agent, "_call_llm", return_value='{"critiques": []}') as llamada:
            agent.critique("ctx", _output("01", "A01", []), [_output("03", "A03", ["H"])])
        assert '"target_agent_id": "03"' in llamada.call_args.args[0]

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

    def _mock_agents(self, mock_a01_cls, mock_a02_cls, mock_a03_cls):
        a01 = MagicMock()
        a01.AGENT_ID = "01"
        a01.AGENT_NAME = "Analista de Literatura"
        a01.critique.return_value = [_critique("01", "A01", "03", "hipótesis clínica B", "MEDIUM")]
        a01.revise.return_value = _output("01", "A01", ["hipótesis literatura revisada"])
        mock_a01_cls.return_value = a01

        # Agente 02 no tiene output en Ronda 1 (los tests base lo excluyen del debate)
        a02 = MagicMock()
        a02.AGENT_ID = "02"
        a02.AGENT_NAME = "Especialista Genómica"
        mock_a02_cls.return_value = a02

        a03 = MagicMock()
        a03.AGENT_ID = "03"
        a03.AGENT_NAME = "Consultor Clínico"
        a03.critique.return_value = [_critique("03", "A03", "01", "hipótesis literatura A", "LOW")]
        a03.revise.return_value = _output("03", "A03", ["hipótesis clínica revisada"])
        mock_a03_cls.return_value = a03

        return a01, a02, a03

    def _patch_all_agents(self):
        return (
            patch("backend.pipeline.debate.LiteratureAnalystAgent"),
            patch("backend.pipeline.debate.GenomicsSpecialistAgent"),
            patch("backend.pipeline.debate.ClinicalConsultantAgent"),
        )

    def test_run_debate_produce_report_con_3_rondas(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        r1 = self._make_round1_report()

        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.GenomicsSpecialistAgent") as M02, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_agents(M01, M02, M03)
            report = asyncio.run(run_debate(case, r1))

        assert len(report.debate_rounds) == 3
        assert report.debate_rounds[0].round_number == 2
        assert report.debate_rounds[1].round_number == 3
        assert report.debate_rounds[2].round_number == 4

    def test_run_debate_preserva_agent_outputs_ronda1(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        r1 = self._make_round1_report()

        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.GenomicsSpecialistAgent") as M02, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_agents(M01, M02, M03)
            report = asyncio.run(run_debate(case, r1))

        assert len(report.agent_outputs) == 2

    def test_run_debate_hipotesis_finales_son_de_ronda4(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        r1 = self._make_round1_report()

        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.GenomicsSpecialistAgent") as M02, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_agents(M01, M02, M03)
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
             patch("backend.pipeline.debate.GenomicsSpecialistAgent") as M02, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_agents(M01, M02, M03)
            report = asyncio.run(run_debate(case, r1))

        ronda2 = report.debate_rounds[0]
        assert ronda2.round_number == 2
        assert len(ronda2.critiques) == 2  # Agente 02 excluido (sin output en Ronda 1)


# ── Tests: el debate cuando un agente se cayó en la Ronda 1 ────────────────────

class TestDebateConAgenteCaido:
    """
    run_round_1() deja fuera de agent_outputs a los agentes que fallaron, así que
    el debate recibe menos outputs que agentes instanciados. Antes se indexaba
    outputs_by_id[agent.AGENT_ID] sin filtrar y saltaba KeyError, que tumbaba
    /api/analyze entero.
    """

    def _solo_agente_01(self) -> Report:
        """Ronda 1 en la que los Agentes 02 y 03 fallaron y no dejaron output."""
        return Report(
            case_summary="Narrativa de prueba.",
            hypotheses=[_hypothesis("hipótesis literatura A")],
            agent_outputs=[_output("01", "Analista de Literatura", ["hipótesis literatura A"])],
            sources_summary={"I": 0, "II": 1, "III": 0},
        )

    def _mock_ambos(self, M01, M03):
        a01 = MagicMock()
        a01.AGENT_ID = "01"
        a01.AGENT_NAME = "Analista de Literatura"
        a01.critique.return_value = []
        a01.revise.return_value = _output("01", "A01", ["revisada 01"])
        M01.return_value = a01

        a03 = MagicMock()
        a03.AGENT_ID = "03"
        a03.AGENT_NAME = "Consultor Clínico"
        a03.critique.return_value = []
        a03.revise.return_value = _output("03", "A03", ["revisada 03"])
        M03.return_value = a03
        return a01, a03

    def test_no_levanta_keyerror_si_falta_un_agente(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_ambos(M01, M03)
            report = asyncio.run(run_debate(case, self._solo_agente_01()))
        assert isinstance(report, Report)

    def test_deja_constancia_del_agente_ausente(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_ambos(M01, M03)
            report = asyncio.run(run_debate(case, self._solo_agente_01()))
        assert len(report.absent_agents) == 2
        assert any("02" in a for a in report.absent_agents)
        assert any("03" in a for a in report.absent_agents)

    def test_con_un_solo_agente_no_simula_rondas(self):
        """Sin contrincante no hay debate adversarial: mejor 0 rondas que 3 vacías."""
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            a01, a03 = self._mock_ambos(M01, M03)
            report = asyncio.run(run_debate(case, self._solo_agente_01()))

        assert report.debate_rounds == []
        assert [h.text for h in report.hypotheses] == ["hipótesis literatura A"]
        # No se gastan llamadas al LLM en un debate que no puede ocurrir
        a01.critique.assert_not_called()
        a01.revise.assert_not_called()
        a03.critique.assert_not_called()

    def test_debate_completo_no_reporta_ausentes(self):
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        r1 = Report(
            case_summary="s",
            agent_outputs=[
                _output("01", "Analista de Literatura", ["a"]),
                _output("02", "Especialista Genómica", ["c"]),
                _output("03", "Consultor Clínico", ["b"]),
            ],
        )
        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.GenomicsSpecialistAgent") as M02, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_ambos(M01, M03)
            a02 = MagicMock()
            a02.AGENT_ID = "02"
            a02.AGENT_NAME = "Especialista Genómica"
            a02.critique.return_value = []
            a02.revise.return_value = _output("02", "A02", ["revisada 02"])
            M02.return_value = a02
            report = asyncio.run(run_debate(case, r1))

        assert report.absent_agents == []
        assert len(report.debate_rounds) == 3

    def test_falla_claro_si_ningun_id_coincide(self):
        """Un output con un agent_id desconocido no debe dar KeyError sino un error legible."""
        case = ClinicalCase(raw_text="texto", pico=_make_pico())
        r1 = Report(
            case_summary="s",
            agent_outputs=[_output("99", "Agente Fantasma", ["x"])],
        )
        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            self._mock_ambos(M01, M03)
            with pytest.raises(RuntimeError, match="numeración de agentes"):
                asyncio.run(run_debate(case, r1))


# ── Tests: debate con los tres agentes de la Ronda 1 ─────────────────────────

class TestDebateConTresAgentes:
    def _agente(self, agent_id: str, nombre: str) -> MagicMock:
        a = MagicMock()
        a.AGENT_ID = agent_id
        a.AGENT_NAME = nombre
        a.critique.return_value = []
        a.revise.return_value = _output(agent_id, nombre, [f"revisada {agent_id}"])
        return a

    def _correr(self, case: ClinicalCase):
        r1 = Report(case_summary="s", agent_outputs=[
            _output("01", "Analista de Literatura", ["h01"]),
            _output("02", "Especialista Genómica", ["h02"]),
            _output("03", "Consultor Clínico", ["h03"]),
        ])
        agentes = {i: self._agente(i, n) for i, n in [
            ("01", "Analista de Literatura"), ("02", "Especialista Genómica"), ("03", "Consultor Clínico"),
        ]}
        with patch("backend.pipeline.debate.LiteratureAnalystAgent", return_value=agentes["01"]), \
             patch("backend.pipeline.debate.GenomicsSpecialistAgent", return_value=agentes["02"]), \
             patch("backend.pipeline.debate.ClinicalConsultantAgent", return_value=agentes["03"]), \
             patch("backend.pipeline.genomic_context.PharmGKBClient") as pharm, \
             patch("backend.pipeline.genomic_context.ClinVarClient") as clinvar:
            report = asyncio.run(run_debate(case, r1))
        return report, agentes, pharm, clinvar

    def test_ronda2_hace_una_critica_por_agente_con_los_otros_dos_outputs(self):
        _, agentes, _, _ = self._correr(ClinicalCase(raw_text="texto", pico=_make_pico()))
        for agent_id, agente in agentes.items():
            assert agente.critique.call_count == 1
            otros = agente.critique.call_args.args[2]
            assert sorted(o.agent_id for o in otros) == sorted({"01", "02", "03"} - {agent_id})

    def test_hipotesis_finales_incluyen_al_agente_02(self):
        report, _, _, _ = self._correr(ClinicalCase(raw_text="texto", pico=_make_pico()))
        assert "revisada 02" in [h.text for h in report.hypotheses]

    def test_sin_perfil_genomico_previo_no_consulta_apis_externas(self):
        _, _, pharm, clinvar = self._correr(ClinicalCase(raw_text="texto", pico=_make_pico()))
        pharm.assert_not_called()
        clinvar.assert_not_called()
