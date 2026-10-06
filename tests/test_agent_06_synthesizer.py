"""
Tests del Agente 06 — Sintetizador (Sprint 4).

`_call_llm` se reemplaza en cada test: ninguno llama a un LLM real ni a la red.
Caso base: neuropatía axonal sensitivomotora, paciente masculino de 42 años.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

import pytest

from backend.agents import agent_06_synthesizer as ag06
from backend.agents.agent_06_synthesizer import SynthesizerAgent, check_invention
from backend.api.schemas import (
    CaseSummarySection,
    DebateSummary,
    RankedHypothesis,
    ReportMetadata,
    StructuredReport,
)
from backend.mock.mode import ENV_VAR
from backend.models.hypothesis import Source
from backend.models.trial import ClinicalTrial

PMID_OK = "12345678"
NCT_OK = "NCT01234567"


def _report() -> StructuredReport:
    return StructuredReport(
        metadata=ReportMetadata(
            generated_at=dt.datetime(2026, 10, 6), nexus_version="test",
            processing_time_seconds=1.0,
        ),
        case_summary=CaseSummarySection(
            narrative="Varón de 42 años con neuropatía axonal sensitivomotora. EMG compatible.",
        ),
        hypotheses=[
            RankedHypothesis(
                rank=1, text="Amiloidosis hereditaria por TTR", priority="HIGH",
                evidence_level="II", rationale="Neuropatía axonal progresiva.",
                supporting_agents=["01"], status="respaldada",
                sources=[Source(pmid=PMID_OK, title="TTR amyloidosis",
                                verified=True, verification_status="verificada")],
            ),
        ],
        debate_summary=DebateSummary(
            rounds_completed=3, total_critiques=2, divergences=[], consensus_reached=True,
        ),
        clinical_trials=[
            ClinicalTrial(nct_id=NCT_OK, title="Tafamidis in ATTR", status="RECRUITING",
                          brief_summary="..."),
        ],
        bibliography=[],
    )


def _run(agent: SynthesizerAgent, respuesta: str | Exception) -> str | None:
    def fake(prompt: str, *, task: str) -> str:
        assert task == "agente06_sintesis"
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta
    agent._call_llm = fake  # type: ignore[method-assign]
    return asyncio.run(agent.synthesize(_report()))


@pytest.fixture(autouse=True)
def _sin_mock(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)


def test_resumen_valido_se_acepta():
    texto = (f"La hipótesis principal sugiere amiloidosis por TTR (PMID {PMID_OK}), "
             f"con evidencia II. El ensayo {NCT_OK} podría ser relevante.")
    assert _run(SynthesizerAgent(), texto) == texto


def test_pmid_inventado_descarta():
    assert _run(SynthesizerAgent(), "Respaldado por PMID 99999999.") is None


def test_nct_inventado_descarta():
    assert _run(SynthesizerAgent(), "Ver el ensayo NCT09999999.") is None


def test_gen_inventado_descarta():
    assert _run(SynthesizerAgent(), "Podría explicarse por una variante en MFN2.") is None


def test_siglas_clinicas_no_son_genes():
    assert _run(SynthesizerAgent(), "El EMG y la CMT se mencionan como contexto.") is not None


def test_excepcion_del_llm_devuelve_none():
    assert _run(SynthesizerAgent(), RuntimeError("cuota")) is None


def test_respuesta_vacia_devuelve_none():
    assert _run(SynthesizerAgent(), "   ") is None


def test_check_invention_devuelve_el_token_infractor():
    assert check_invention("Ver NCT09999999", _report()) == "NCT09999999"
    assert check_invention("Texto limpio sobre TTR", _report()) is None


def test_modo_mock_no_llama_al_proveedor(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "1")
    monkeypatch.setenv("GROQ_API_KEY", "")
    # Sin grabación devuelve "{}" y queda None; con grabación, texto. Ninguno toca la red.
    resultado = asyncio.run(SynthesizerAgent().synthesize(_report()))
    assert resultado is None or isinstance(resultado, str)


def test_no_importa_groq_directamente():
    fuente = Path(ag06.__file__).read_text(encoding="utf-8")
    assert "import groq" not in fuente and "from groq" not in fuente


def test_vocabulario_genomico_no_es_gen():
    assert check_invention("Secuenciar el genoma para buscar CNV y VUS.", _report()) is None


# ── Solo se cita lo confirmado contra PubMed ──────────────────────────────────

PMID_MALO = "87654321"


def _report_con_fuente(estado: str | None, *, en_bibliografia: str | None = None) -> StructuredReport:
    """Reporte con una segunda fuente (PMID_MALO) en el estado de verificación dado."""
    r = _report()
    r.hypotheses[0].sources.append(
        Source(pmid=PMID_MALO, title="Otro artículo", verification_status=estado)
    )
    if en_bibliografia is not None:
        r.bibliography.append(
            Source(pmid=PMID_MALO, title="Otro artículo", verification_status=en_bibliografia)
        )
    return r


@pytest.mark.parametrize("estado", ["inexistente", "discordante", "no_verificable", None])
def test_pmid_no_confirmado_descarta(estado):
    r = _report_con_fuente(estado)
    assert check_invention(f"Respaldada por PMID {PMID_MALO}.", r) == PMID_MALO


def test_pmid_confirmado_pasa():
    r = _report_con_fuente("verificada")
    assert check_invention(f"Respaldada por PMID {PMID_MALO}.", r) is None


def test_pmid_con_estados_mixtos_se_trata_como_no_confirmado():
    # Confirmado en la bibliografía pero refutado en la hipótesis: criterio conservador.
    r = _report_con_fuente("discordante", en_bibliografia="verificada")
    assert check_invention(f"Ver PMID {PMID_MALO}.", r) == PMID_MALO


def test_pmid_confirmado_en_bibliografia_sin_fuente_en_hipotesis_pasa():
    r = _report()
    r.bibliography.append(Source(pmid=PMID_MALO, title="X", verification_status="verificada"))
    assert check_invention(f"Ver PMID {PMID_MALO}.", r) is None


def test_resumen_con_pmid_refutado_se_descarta_entero():
    r = _report_con_fuente("inexistente")

    def fake(prompt: str, *, task: str) -> str:
        return f"Sugiere amiloidosis (PMID {PMID_OK}) y también PMID {PMID_MALO}."
    agent = SynthesizerAgent()
    agent._call_llm = fake  # type: ignore[method-assign]
    assert asyncio.run(agent.synthesize(r)) is None


@pytest.mark.parametrize("estado", ["inexistente", "discordante", "no_verificable", None])
def test_contexto_no_ofrece_pmids_no_confirmados(estado):
    ctx = ag06.build_context(_report_con_fuente(estado))
    assert PMID_MALO not in ctx
    assert PMID_OK in ctx
    assert "no confirmada" in ctx


def test_contexto_lista_los_confirmados_y_el_prompt_lo_exige():
    ctx = ag06.build_context(_report_con_fuente("verificada"))
    assert PMID_OK in ctx and PMID_MALO in ctx
    assert "confirmados" in ctx.lower()
    assert "confirmad" in SynthesizerAgent.SYSTEM_PROMPT


def test_contexto_con_pmid_de_estados_mixtos_no_lo_ofrece():
    ctx = ag06.build_context(_report_con_fuente("discordante", en_bibliografia="verificada"))
    assert PMID_MALO not in ctx


def test_biomarker_extractor_importa_sin_ciclo():
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "-c", "import backend.ingestion.biomarker_extractor"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


# ── Recorte del contexto: ensayos y verificación nunca se pierden ─────────────

def _report_largo(n_hipotesis: int = 8, largo: int = 1500) -> StructuredReport:
    """Reporte cuyo texto libre excede por mucho el límite del contexto."""
    r = _report()
    r.case_summary.narrative = "Narrativa clínica extensa. " * 200
    r.hypotheses = [
        RankedHypothesis(
            rank=i, text=f"Hipótesis número {i} sobre neuropatía", priority="HIGH",
            evidence_level="II", rationale=("Fundamento largo. " * 200)[:largo],
            supporting_agents=["01"], status="respaldada",
            arbiter_note=("Nota del árbitro. " * 200)[:largo],
            sources=[Source(pmid=f"1000000{i}", title="T", verified=True,
                            verification_status="verificada")],
        )
        for i in range(1, n_hipotesis + 1)
    ]
    r.clinical_trials = [
        ClinicalTrial(nct_id=f"NCT0000000{i}", title=f"Ensayo {i}", status="RECRUITING",
                      brief_summary="...")
        for i in range(1, 6)
    ]
    return r


def test_contexto_corto_queda_identico_al_de_antes():
    esperado = (
        "=== Caso ===\nVarón de 42 años con neuropatía axonal sensitivomotora. "
        "EMG compatible.\n\n=== Hipótesis priorizadas ===\n"
        "1. [prioridad HIGH / EBM II / respaldada] Amiloidosis hereditaria por TTR — "
        "Neuropatía axonal progresiva. (PMIDs confirmados: 12345678; "
        "1 referencia(s) no confirmada(s), no citar)\n\n=== Ensayos clínicos ===\n"
        "- NCT01234567 (sin_evaluar): Tafamidis in ATTR\n\n"
        "=== Verificación bibliográfica ===\nFuentes: 0, verificadas: 0, discordantes: 0, "
        "inexistentes: 0. Hipótesis respaldadas: 0, pendientes: 0, especulativas: 0."
    )
    assert ag06.build_context(_report_con_fuente("inexistente")) == esperado


def test_recorte_conserva_ensayos_y_verificacion_completos():
    r = _report_largo()
    ctx = ag06.build_context(r)
    assert len(ctx) <= ag06._MAX_CONTEXT_CHARS
    for t in r.clinical_trials:
        assert f"- {t.nct_id} ({t.compatibility}): {t.title}" in ctx
    assert "=== Verificación bibliográfica ===" in ctx
    assert ctx.rstrip().endswith("especulativas: 0.")


def test_recorte_conserva_cada_hipotesis_con_sus_pmids():
    r = _report_largo()
    ctx = ag06.build_context(r)
    for h in r.hypotheses:
        assert f"{h.rank}. [prioridad HIGH / EBM II / respaldada] {h.text} — " in ctx
        assert f"(PMIDs confirmados: 1000000{h.rank})" in ctx


def test_recorte_se_marca_y_es_determinista():
    r = _report_largo()
    ctx = ag06.build_context(r)
    assert "[...]" in ctx
    assert ctx == ag06.build_context(r)


def test_recorte_acorta_lo_mas_largo_y_deja_lo_corto():
    r = _report_largo()
    r.hypotheses[0].rationale = "Fundamento breve."
    ctx = ag06.build_context(r)
    assert "— Fundamento breve. (PMIDs" in ctx


def test_caso_patologico_no_pierde_bloques_aunque_exceda_el_limite():
    r = _report_largo(n_hipotesis=60, largo=50)
    for h in r.hypotheses:
        h.text = "Enunciado extenso " * 12
    ctx = ag06.build_context(r)
    assert len(ctx) > ag06._MAX_CONTEXT_CHARS  # documentado: lo obligatorio no se recorta
    assert "=== Ensayos clínicos ===" in ctx
    assert ctx.rstrip().endswith("especulativas: 0.")
    assert all(f"(PMIDs confirmados: 1000000" in ctx for _ in [0])
    assert ctx.count("(PMIDs confirmados:") == 60


def test_el_prompt_pide_no_introducir_siglas():
    p = SynthesizerAgent.SYSTEM_PROMPT
    assert "siglas" in p and "abreviaturas" in p and "palabras" in p
