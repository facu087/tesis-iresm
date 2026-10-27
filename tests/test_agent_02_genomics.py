"""
Tests del Agente 02 — Especialista Genómica (backend/agents/agent_02_genomics.py).

Tests unitarios: _call_llm siempre mockeado, sin llamadas a Groq ni a PharmGKB.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.agents.agent_02_genomics import GenomicsSpecialistAgent
from backend.models.genomics import (
    GenomicContext,
    GenomicSource,
    GenomicSourceStatus,
    PharmacogenomicAnnotation,
)
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
        def capturar(prompt: str, **kwargs) -> str:
            prompts_capturados.append(prompt)
            return _json_valido()
        with patch.object(agente, "_call_llm", side_effect=capturar):
            agente.run("contexto clínico")
        assert prompts_capturados
        assert "No se reportan variantes" in prompts_capturados[0]

    def test_run_caso_ttr_prompt_contiene_variante(self):
        agente = GenomicsSpecialistAgent(_ctx_con_ttr())
        prompts_capturados: list[str] = []
        def capturar(prompt: str, **kwargs) -> str:
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
        def capturar(prompt: str, **kwargs) -> str:
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


# ── Guarda en modo con hallazgos (lee case_genetic_findings del JSON crudo) ────

class TestGuardaConHallazgos:
    """
    El modelo `Hypothesis` no tiene `case_genetic_findings`: la guarda lo lee del
    JSON crudo. Antes lo buscaba en la hipótesis parseada y en este modo nunca
    degradaba nada.
    """

    def _run(self, hallazgo: str) -> Priority:
        agente = GenomicsSpecialistAgent(_ctx_con_ttr())
        with patch.object(agente, "_call_llm", return_value=_json_con_hallazgo(hallazgo)):
            return agente.run("contexto").hypotheses[0].priority

    def test_hallazgo_de_otro_gen_inventado_se_degrada(self):
        assert self._run("MFN2 p.Arg94Gln") == Priority.LOW

    def test_variante_real_atribuida_a_otro_gen_se_degrada(self):
        assert self._run("MFN2 p.Val30Met") == Priority.LOW

    @pytest.mark.parametrize("hallazgo", [
        "TTR p.Val30Met", "p.Val30Met", "Val30Met", "variante ttr p.val30met",
    ])
    def test_hallazgo_reportado_con_otra_escritura_no_se_degrada(self, hallazgo):
        assert self._run(hallazgo) != Priority.LOW

    def test_revise_degrada_con_hallazgos_en_el_caso(self):
        agente = GenomicsSpecialistAgent(_ctx_con_ttr())
        own = AgentOutput(agent_id="02", agent_name="Especialista Genómica",
                          hypotheses=[], raw_response="{}")
        with patch.object(agente, "_call_llm", return_value=_json_con_hallazgo("MFN2 p.Arg94Gln")):
            out = agente.revise("contexto", own, [])
        assert out.hypotheses[0].priority == Priority.LOW
        assert out.hypotheses[0].rationale.startswith("ADVERTENCIA")

    def test_no_descarta_la_hipotesis(self):
        agente = GenomicsSpecialistAgent(_ctx_con_ttr())
        with patch.object(agente, "_call_llm", return_value=_json_con_hallazgo("MFN2 p.Arg94Gln")):
            out = agente.run("contexto")
        assert len(out.hypotheses) == 1


def _json_con_texto(texto: str) -> str:
    return (
        f'{{"hypotheses": [{{"text": "{texto}", "priority": "HIGH", '
        f'"evidence_level": "II", "rationale": "r", '
        f'"case_genetic_findings": [], "sources": []}}]}}'
    )


def _ctx_con_carbamazepina() -> GenomicContext:
    """PharmGKB consultado por fármaco: el alelo está en el contexto, no en el paciente."""
    return GenomicContext(annotations=[
        PharmacogenomicAnnotation(
            gene="HLA-B", drug="carbamazepine", level="1A",
            variant="HLA-B*15:02", queried_by="drug",
        ),
    ])


class TestGuardaAlelosYRsids:
    """
    Alelos estrella (CYP2C19*2, HLA-B*15:02) y rsIDs (rs4149056) en el enunciado:
    se degrada el que no aparece en ningún lado del contexto que recibió el
    agente (texto del caso y bloque genómico, PharmGKB incluido), en los dos
    modos. El que sí aparece no se degrada: "solicitar genotipado de
    HLA-B*15:02" es una hipótesis válida cuando PharmGKB trae ese alelo.
    """

    def _run(self, ctx: GenomicContext, texto: str, caso: str = "contexto") -> Priority:
        agente = GenomicsSpecialistAgent(ctx)
        with patch.object(agente, "_call_llm", return_value=_json_con_texto(texto)):
            return agente.run(caso).hypotheses[0].priority

    def test_alelo_estrella_inventado_se_degrada(self):
        assert self._run(_ctx_sin_hallazgos(), "El paciente porta CYP2C19*2") == Priority.LOW

    def test_rsid_inventado_se_degrada(self):
        assert self._run(_ctx_sin_hallazgos(), "Evaluar rs4149056 en SLCO1B1") == Priority.LOW

    def test_alelo_hla_inventado_se_degrada(self):
        assert self._run(_ctx_sin_hallazgos(), "Portador de HLA-B*15:02") == Priority.LOW

    def test_alelo_de_pharmgkb_no_se_degrada(self):
        texto = "Solicitar genotipado de HLA-B*15:02 antes de carbamazepina"
        assert self._run(_ctx_con_carbamazepina(), texto) != Priority.LOW

    def test_alelo_distinto_al_de_pharmgkb_se_degrada(self):
        texto = "Solicitar genotipado de HLA-A*31:01 antes de carbamazepina"
        assert self._run(_ctx_con_carbamazepina(), texto) == Priority.LOW

    def test_alelo_informado_en_el_texto_del_caso_no_se_degrada(self):
        caso = "Estudio farmacogenético previo: CYP2C19*2/*2."
        assert self._run(_ctx_sin_hallazgos(), "Metabolizador lento por CYP2C19*2", caso) != Priority.LOW

    def test_rsid_informado_en_el_texto_del_caso_no_se_degrada(self):
        caso = "Genotipado: rs4149056 heterocigoto."
        assert self._run(_ctx_sin_hallazgos(), "Riesgo de miopatía por RS4149056", caso) != Priority.LOW

    def test_alelo_inventado_se_degrada_con_hallazgos_en_el_caso(self):
        """Con variantes reportadas (modo hallazgos) el control también corre."""
        assert self._run(_ctx_con_ttr(), "TTR p.Val30Met y además CYP2D6*4") == Priority.LOW

    def test_variante_reportada_en_el_texto_sigue_sin_degradarse(self):
        """Comportamiento previo: en modo hallazgos, p./c. reportada en el enunciado pasa."""
        assert self._run(_ctx_con_ttr(), "Amiloidosis por TTR p.Val30Met") != Priority.LOW

    def test_texto_sin_alelos_no_se_degrada(self):
        assert self._run(_ctx_sin_hallazgos(), "Solicitar panel de neuropatías hereditarias") != Priority.LOW

    def test_revise_degrada_alelo_inventado(self):
        agente = GenomicsSpecialistAgent(_ctx_sin_hallazgos())
        own = AgentOutput(agent_id="02", agent_name="Especialista Genómica",
                          hypotheses=[], raw_response="{}")
        with patch.object(agente, "_call_llm", return_value=_json_con_texto("Portador de CYP2C19*2")):
            out = agente.revise("contexto", own, [])
        assert out.hypotheses[0].priority == Priority.LOW
        assert out.hypotheses[0].rationale.startswith("ADVERTENCIA")


class TestAtribucionEnElReporte:
    def test_hipotesis_del_agente_02_en_la_ronda_4_lista_al_especialista(self):
        from backend.models.case import ClinicalCase
        from backend.models.report import DebateRound
        from backend.pipeline.report_builder import build_export

        agente = GenomicsSpecialistAgent(_ctx_con_ttr())
        with patch.object(agente, "_call_llm", return_value=_json_valido(1)):
            out = agente.run("contexto")
        report = Report(
            case_summary="Varón de 42 años con neuropatía axonal sensitivomotora.",
            hypotheses=out.hypotheses,
            debate_rounds=[DebateRound(round_number=4, agent_outputs=[out])],
        )
        exportado = build_export(
            case=ClinicalCase(raw_text="Varón de 42 años con neuropatía axonal."),
            report=report, trials=[], processing_time=1.0,
        )
        assert "Especialista Genómica" in exportado.hypotheses[0].supporting_agents


def test_system_prompt_no_nombra_genes_ni_variantes():
    """La spec pide un prompt genérico: un ejemplo con un gen real sesga al modelo."""
    import re
    from backend.agents import agent_02_genomics as ag02

    prompt = ag02.SYSTEM_PROMPT
    assert not re.search(r"\b[cpg]\.[A-Z0-9]", prompt), "el prompt cita una notación de variante"
    siglas = set(re.findall(r"\b[A-Z][A-Z0-9]{1,7}\b", prompt))
    permitidas = {"NO", "JSON", "ORIENTACIÓN", "HIGH", "MEDIUM", "LOW", "DEBE", "PubMed",
                  "ID", "IDs", "RCT", "RCTs", "II", "III", "I", "X", "CONTEXTO", "GENÓMICO",
                  "ADVERTENCIA", "ÚNICAMENTE", "REGLAS", "FORMATO", "DE"}
    assert siglas <= permitidas, f"siglas con forma de gen en el prompt: {siglas - permitidas}"
