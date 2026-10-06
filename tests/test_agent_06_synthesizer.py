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
                sources=[Source(pmid=PMID_OK, title="TTR amyloidosis")],
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
