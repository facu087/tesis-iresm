"""
Tests del Agente 02 — Especialista Genómica (backend/agents/agent_02_genomics.py).

Tests unitarios: _call_llm siempre mockeado, sin llamadas a Groq ni a PharmGKB.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.agents.agent_02_genomics import GenomicsSpecialistAgent
from backend.models.genomics import GenomicContext, GenomicSource, GenomicSourceStatus
from backend.models.hypothesis import EvidenceLevel, Priority
from backend.models.report import AgentOutput, Report


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _json_valido(n: int = 2) -> str:
    hipotesis = ", ".join(
        f'{{"text": "hipótesis {i}", "priority": "HIGH", "evidence_level": "II", '
        f'"rationale": "razonamiento {i}", "case_genetic_findings": [], "sources": []}}'
        for i in range(1, n + 1)
    )
    return f'{{"hypotheses": [{hipotesis}]}}'


def _json_con_hallazgo(hallazgo: str) -> str:
    return (
        f'{{"hypotheses": [{{"text": "hipótesis sobre {hallazgo}", '
        f'"priority": "HIGH", "evidence_level": "II", "rationale": "r", '
        f'"case_genetic_findings": ["{hallazgo}"], "sources": []}}]}}'
    )


def _ctx_sin_hallazgos() -> GenomicContext:
    return GenomicContext()


def _ctx_con_ttr() -> GenomicContext:
    return GenomicContext(
        variants=["p.Val30Met"],
        genetic_findings=["Variante TTR p.Val30Met"],
        genes=["TTR"],
    )


# ── Identidad y output ────────────────────────────────────────────────────────

class TestIdentidad:
    def test_agent_id(self):
        assert GenomicsSpecialistAgent.AGENT_ID == "02"

    def test_agent_name(self):
        assert GenomicsSpecialistAgent.AGENT_NAME == "Especialista Genómica"

    def test_no_importa_groq(self):
        import ast, pathlib
        src = pathlib.Path("backend/agents/agent_02_genomics.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        imports = [
            node.names[0].name if isinstance(node, ast.Import) else node.module
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        assert "groq" not in imports


class TestRun:
    def test_run_devuelve_agent_output(self):
        agente = GenomicsSpecialistAgent()
        with patch.object(agente, "_call_llm", return_value=_json_valido()):
            out = agente.run("contexto clínico")
        assert isinstance(out, AgentOutput)
        assert out.agent_id == "02"

    def test_run_respuesta_valida(self):
        agente = GenomicsSpecialistAgent()
        with patch.object(agente, "_call_llm", return_value=_json_valido(2)):
            out = agente.run("contexto")
        assert len(out.hypotheses) == 2

    def test_run_6_hipotesis_quedan_4(self):
        agente = GenomicsSpecialistAgent()
        with patch.object(agente, "_call_llm", return_value=_json_valido(6)):
            out = agente.run("contexto")
        assert len(out.hypotheses) <= 4

    def test_run_respuesta_malformada_lanza_error(self):
        agente = GenomicsSpecialistAgent()
        with patch.object(agente, "_call_llm", return_value="esto no es json"):
            with pytest.raises((ValueError, Exception)):
                agente.run("contexto")

    def test_run_caso_base_hace_1_llamada_llm(self):
        agente = GenomicsSpecialistAgent(_ctx_sin_hallazgos())
        with patch.object(agente, "_call_llm", return_value=_json_valido()) as mock_llm:
            agente.run("contexto")
        assert mock_llm.call_count == 1

    def test_run_caso_base_prompt_dice_no_hay_variantes(self):
        agente = GenomicsSpecialistAgent(_ctx_sin_hallazgos())
        prompts_capturados: list[str] = []
        def capturar(prompt: str) -> str:
            prompts_capturados.append(prompt)
            return _json_valido()
        with patch.object(agente, "_call_llm", side_effect=capturar):
            agente.run("contexto clínico")
        assert prompts_capturados
        assert "No se reportan variantes" in prompts_capturados[0]

    def test_run_caso_ttr_prompt_contiene_variante(self):
        agente = GenomicsSpecialistAgent(_ctx_con_ttr())
        prompts_capturados: list[str] = []
        def capturar(prompt: str) -> str:
            prompts_capturados.append(prompt)
            return _json_valido()
        with patch.object(agente, "_call_llm", side_effect=capturar):
            agente.run("contexto clínico")
        assert "p.Val30Met" in prompts_capturados[0]


# ── Guarda anti-invención ─────────────────────────────────────────────────────

class TestGuardaAntiInvencion:
    def test_hallazgo_real_no_se_degrada(self):
        """TTR p.Val30Met está en el contexto → no se degrada."""
        agente = GenomicsSpecialistAgent(_ctx_con_ttr())
        with patch.object(agente, "_call_llm", return_value=_json_con_hallazgo("p.Val30Met")):
            out = agente.run("contexto")
        assert out.hypotheses[0].priority != Priority.LOW

    def test_hallazgo_inventado_se_degrada(self):
        """p.Arg50Trp no está en el contexto → prioridad LOW."""
        agente = GenomicsSpecialistAgent(_ctx_sin_hallazgos())
        with patch.object(agente, "_call_llm", return_value=_json_con_hallazgo("p.Arg50Trp")):
            out = agente.run("contexto")
        assert out.hypotheses[0].priority == Priority.LOW

    def test_hallazgo_inventado_tiene_advertencia_en_rationale(self):
        agente = GenomicsSpecialistAgent(_ctx_sin_hallazgos())
        with patch.object(agente, "_call_llm", return_value=_json_con_hallazgo("p.Arg50Trp")):
            out = agente.run("contexto")
        assert out.hypotheses[0].rationale.startswith("ADVERTENCIA")

    def test_modo_orientacion_variante_en_texto_se_degrada(self):
        """En modo orientación (sin hallazgos) la hipótesis no debería citar variantes concretas."""
        json_con_variante = (
            '{"hypotheses": [{"text": "Evaluar variante p.Arg50Trp en TTR", '
            '"priority": "HIGH", "evidence_level": "II", "rationale": "r", '
            '"case_genetic_findings": [], "sources": []}]}'
        )
        agente = GenomicsSpecialistAgent(_ctx_sin_hallazgos())
        with patch.object(agente, "_call_llm", return_value=json_con_variante):
            out = agente.run("contexto")
        assert out.hypotheses[0].priority == Priority.LOW


# ── critique y revise ─────────────────────────────────────────────────────────

class TestDebateMethods:
    def test_critique_incluye_bloque_genomico_en_prompt(self):
        ctx = _ctx_con_ttr()
        agente = GenomicsSpecialistAgent(ctx)
        prompts_capturados: list[str] = []
        def capturar(prompt: str) -> str:
            prompts_capturados.append(prompt)
            return '{"critiques": []}'
        own = AgentOutput(agent_id="02", agent_name="Especialista Genómica", hypotheses=[], raw_response="{}")
        with patch.object(agente, "_call_llm", side_effect=capturar):
            agente.critique("contexto", own, [])
        assert any("CONTEXTO GENÓMICO" in p for p in prompts_capturados)

    def test_revise_4_hipotesis_maximas(self):
        agente = GenomicsSpecialistAgent()
        own = AgentOutput(agent_id="02", agent_name="Especialista Genómica", hypotheses=[], raw_response="{}")
        with patch.object(agente, "_call_llm", return_value=_json_valido(6)):
            out = agente.revise("contexto", own, [])
        assert len(out.hypotheses) <= 4

    def test_revise_aplica_guarda(self):
        agente = GenomicsSpecialistAgent(_ctx_sin_hallazgos())
        own = AgentOutput(agent_id="02", agent_name="Especialista Genómica", hypotheses=[], raw_response="{}")
        with patch.object(agente, "_call_llm", return_value=_json_con_hallazgo("p.Arg50Trp")):
            out = agente.revise("contexto", own, [])
        assert out.hypotheses[0].priority == Priority.LOW


# ── Atribución en el reporte ──────────────────────────────────────────────────

class TestAtribucion:
    def test_agent_output_contiene_agent_id_correcto(self):
        """El AgentOutput producido por Ag02 tiene agent_id '02'."""
        agente = GenomicsSpecialistAgent()
        with patch.object(agente, "_call_llm", return_value=_json_valido()):
            out = agente.run("contexto")
        assert out.agent_id == "02"
        assert out.agent_name == "Especialista Genómica"

    def test_hipotesis_ronda4_agente02_aparece_en_supporting_agents(self):
        """
        Un Report con una hipótesis del Ag02 en la Ronda 4 pasa por build_export()
        y la hipótesis exportada lista 'Especialista Genómica' en supporting_agents.
        """
        from backend.models.case import ClinicalCase, PICOSynthesis
        from backend.models.hypothesis import Hypothesis
        from backend.models.report import DebateRound, Report
        from backend.models.trial import ClinicalTrial
        from backend.pipeline.report_builder import build_export

        texto_hipotesis = "Evaluar variante TTR p.Val30Met como causa de amiloidosis"

        h = Hypothesis(
            text=texto_hipotesis,
            priority=Priority.HIGH,
            evidence_level=EvidenceLevel.II,
            rationale="Variante patogénica en contexto clínico compatible.",
        )

        # Output de Ronda 1 (Ag02 participa)
        out_r1 = AgentOutput(
            agent_id="02",
            agent_name="Especialista Genómica",
            hypotheses=[h],
            raw_response="{}",
        )

        # Output de Ronda 4 (revisión final del Ag02)
        out_r4 = AgentOutput(
            agent_id="02",
            agent_name="Especialista Genómica",
            hypotheses=[h],
            raw_response="{}",
        )

        ronda4 = DebateRound(round_number=4, agent_outputs=[out_r4])

        report = Report(
            case_summary="Caso de prueba.",
            hypotheses=[h],
            agent_outputs=[out_r1],
            debate_rounds=[ronda4],
            sources_summary={"I": 0, "II": 0, "III": 0},
        )

        pico = PICOSynthesis(
            patient_profile="Masculino 67 años",
            chief_complaint="Polineuropatía axonal",
            relevant_history=[],
            negative_findings=[],
            disease_duration="2 años",
            current_treatments=[],
            procedures_done=[],
            comparison="No aplica",
            primary_outcome="Identificar etiología",
            secondary_outcomes=[],
            biomarkers=[],
            genetic_findings=[],
            clinical_narrative="Narrativa de prueba.",
        )
        case = ClinicalCase(raw_text="texto", pico=pico)

        structured = build_export(case, report, [], 1.0)
        hipotesis_exportada = next(
            h for h in structured.hypotheses if texto_hipotesis in h.text
        )
        assert "Especialista Genómica" in hipotesis_exportada.supporting_agents
