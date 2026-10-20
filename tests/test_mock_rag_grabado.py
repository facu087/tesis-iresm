"""
El modo mock reproduce lo que el RAG ofreció en la corrida grabada.

Sin esto, el modo mock consultaba PubMed en vivo: medido el 2026-10-15, PubMed
ya devolvía otros artículos que el 2026-10-07, las recitaciones grabadas citaban
PMIDs que no se ofrecían, la Ronda 5 los rechazaba y el resumen del Agente 06 se
descartaba. Ningún test toca la red.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from backend.mock import recorder, regenerar
from backend.mock import responses as mock_responses
from backend.mock.mode import ENV_VAR
from backend.mock.responses import RespuestasGrabadasInvalidas
from backend.models.case import ClinicalCase
from backend.pipeline.orchestrator import _enrich_context_with_rag

_ARTICULOS = [
    {"pmid": "15367864", "title": "IgM paraproteinaemic neuropathies.", "journal": "J",
     "year": "2004", "excerpt": "..."},
    {"pmid": "38513047", "title": "Otro artículo", "journal": "K", "year": "2024", "excerpt": ""},
]
_CONTEXTO = "LITERATURA CIENTÍFICA RELEVANTE (fuente: PubMed):\n--- Referencia 1 ---\nPMID 15367864"


def _caso() -> ClinicalCase:
    from tests.test_debate import _make_pico
    return ClinicalCase(raw_text="texto", pico=_make_pico())


def _archivo_grabadas(tmp_path, monkeypatch, rag: dict | None) -> None:
    datos = json.loads(mock_responses._ARCHIVO_GRABADAS.read_text(encoding="utf-8"))
    datos.pop("rag", None)
    if rag is not None:
        datos["rag"] = rag
    destino = tmp_path / "grabadas.json"
    destino.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(mock_responses, "_ARCHIVO_GRABADAS", destino)
    monkeypatch.setattr(mock_responses, "_CACHE", None)


# ── Grabador ────────────────────────────────────────────────────────────────

def test_el_grabador_escribe_el_bloque_rag(tmp_path):
    token = recorder.open_recorder()
    recorder.record_rag(context=_CONTEXTO, articles=_ARTICULOS)
    recorder.close_recorder(token, output_path=tmp_path / "grabacion.json")
    escrito = json.loads((tmp_path / "grabacion.json").read_text(encoding="utf-8"))
    assert escrito["rag"] == {"context": _CONTEXTO, "articles": _ARTICULOS}


def test_sin_grabador_abierto_record_rag_no_hace_nada():
    recorder.record_rag(context=_CONTEXTO, articles=_ARTICULOS)
    assert recorder.current() is None


# ── Conversión a grabadas.json ──────────────────────────────────────────────

_ENTRADA = {"seq": 1, "task": "pico_sintesis", "agent_id": None, "model": "m",
            "truncated": False, "response": "{}"}


def test_regenerar_copia_el_bloque_rag():
    datos = regenerar.construir_grabadas(
        {"generated_at": "2026-10-20T10:00:00+00:00", "entries": [_ENTRADA],
         "rag": {"context": _CONTEXTO, "articles": _ARTICULOS}},
    )
    assert datos["rag"] == {"context": _CONTEXTO, "articles": _ARTICULOS}


def test_regenerar_sin_rag_no_lo_inventa():
    datos = regenerar.construir_grabadas(
        {"generated_at": "2026-10-20T10:00:00+00:00", "entries": [_ENTRADA]},
    )
    assert "rag" not in datos


@pytest.mark.parametrize("rag", [
    {"articles": _ARTICULOS},
    {"context": _CONTEXTO, "articles": [{"title": "sin pmid"}]},
    "no es un objeto",
])
def test_regenerar_rechaza_un_rag_malformado(rag):
    with pytest.raises(regenerar.GrabacionInvalida):
        regenerar.construir_grabadas(
            {"generated_at": "2026-10-20T10:00:00+00:00", "entries": [_ENTRADA], "rag": rag},
        )


# ── Cargador ────────────────────────────────────────────────────────────────

def test_cargador_sin_rag_devuelve_none(tmp_path, monkeypatch):
    _archivo_grabadas(tmp_path, monkeypatch, None)
    assert mock_responses.get_recorded_rag() is None


def test_cargador_con_rag(tmp_path, monkeypatch):
    _archivo_grabadas(tmp_path, monkeypatch, {"context": _CONTEXTO, "articles": _ARTICULOS})
    assert mock_responses.get_recorded_rag()["articles"][1]["pmid"] == "38513047"


def test_cargador_rechaza_un_rag_malformado(tmp_path, monkeypatch):
    _archivo_grabadas(tmp_path, monkeypatch, {"context": 3, "articles": []})
    with pytest.raises(RespuestasGrabadasInvalidas):
        mock_responses.get_recorded_rag()


# ── Orquestador ─────────────────────────────────────────────────────────────

def test_mock_con_rag_grabado_no_consulta_pubmed(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_VAR, "1")
    _archivo_grabadas(tmp_path, monkeypatch, {"context": _CONTEXTO, "articles": _ARTICULOS})
    with patch("backend.pipeline.orchestrator.index_from_clinical_context") as indexar, \
         patch("backend.pipeline.orchestrator.PubMedRetriever") as recuperador:
        contexto, articulos = asyncio.run(_enrich_context_with_rag(_caso(), "BASE"))
    indexar.assert_not_called()
    recuperador.assert_not_called()
    assert contexto == f"BASE\n\n{_CONTEXTO}"
    assert [a.pmid for a in articulos] == ["15367864", "38513047"]


def test_mock_sin_rag_grabado_sigue_consultando(tmp_path, monkeypatch):
    """Una grabación anterior al bloque `rag` se comporta como antes."""
    monkeypatch.setenv(ENV_VAR, "1")
    _archivo_grabadas(tmp_path, monkeypatch, None)

    async def indexar(**_):
        return None

    with patch("backend.pipeline.orchestrator.index_from_clinical_context", side_effect=indexar), \
         patch("backend.pipeline.orchestrator.PubMedRetriever") as recuperador:
        recuperador.return_value.get_context_with_articles.return_value = ("VIVO", [])
        contexto, _ = asyncio.run(_enrich_context_with_rag(_caso(), "BASE"))
    recuperador.assert_called_once()
    assert contexto == "BASE\n\nVIVO"


def test_modo_real_con_grabador_abierto_graba_lo_ofrecido(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)

    class _Articulo:
        def __init__(self, a):
            self.__dict__.update(a)

    async def indexar(**_):
        return None

    token = recorder.open_recorder()
    try:
        with patch("backend.pipeline.orchestrator.index_from_clinical_context", side_effect=indexar), \
             patch("backend.pipeline.orchestrator.PubMedRetriever") as recuperador:
            recuperador.return_value.get_context_with_articles.return_value = (
                _CONTEXTO, [_Articulo(a) for a in _ARTICULOS],
            )
            asyncio.run(_enrich_context_with_rag(_caso(), "BASE"))
        grabado = recorder.current().rag
    finally:
        recorder._current.reset(token)
    assert grabado["context"] == _CONTEXTO
    assert [a["pmid"] for a in grabado["articles"]] == ["15367864", "38513047"]
