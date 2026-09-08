"""
Tests de la configuración de embeddings del RAG.

Estos tests NO cargan modelos reales: stubean `sentence_transformers` y la
función de embedding de ChromaDB. Así corren igual con o sin torch instalado,
que es la única forma de que sean estables en CI y en las máquinas del equipo.

Se usa EphemeralClient (en memoria) para no tocar ./chroma_db/.
"""

from __future__ import annotations

import re
import sys

import chromadb
import pytest

from backend.rag import chroma_store as cs


# ── Stubs ─────────────────────────────────────────────────────────

class _StubEmbeddingFunction:
    """Función de embedding falsa: vectores fijos de 4 dimensiones."""

    def __init__(self, model_name: str = "stub", **kwargs) -> None:
        self.model_name = model_name

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        return [[0.1, 0.2, 0.3, 0.4] for _ in input]

    # ChromaDB >=1.x pide estos métodos para serializar la colección
    def name(self) -> str:
        return "stub"

    @staticmethod
    def build_from_config(config):
        return _StubEmbeddingFunction()

    def get_config(self) -> dict:
        return {}


@pytest.fixture
def nombre(request) -> str:
    """
    Nombre de colección único por test.

    `chromadb.EphemeralClient()` devuelve una instancia compartida para las
    mismas Settings, así que las colecciones sobreviven entre tests. Aislar por
    nombre es más robusto que depender de un reset del cliente.
    """
    limpio = re.sub(r"[^a-zA-Z0-9_]", "_", request.node.name)
    return f"t_{limpio}"[:60]


@pytest.fixture
def con_sentence_transformers(monkeypatch):
    """Simula que sentence-transformers está instalado, sin cargar nada."""
    monkeypatch.setitem(sys.modules, "sentence_transformers", object())
    from chromadb.utils import embedding_functions

    monkeypatch.setattr(
        embedding_functions,
        "SentenceTransformerEmbeddingFunction",
        _StubEmbeddingFunction,
    )


@pytest.fixture
def sin_sentence_transformers(monkeypatch):
    """Simula que sentence-transformers NO está instalado."""
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("simulado: no instalado")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)


# ── resolve_embedding_model ───────────────────────────────────────

def test_default_es_el_modelo_biomedico(monkeypatch):
    monkeypatch.delenv("NEXUS_EMBEDDING_MODEL", raising=False)
    assert cs.resolve_embedding_model() == cs.BIOMEDICAL_EMBEDDING_MODEL


def test_variable_de_entorno_sobreescribe_el_default(monkeypatch):
    monkeypatch.setenv("NEXUS_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    assert cs.resolve_embedding_model() == "all-MiniLM-L6-v2"


def test_argumento_explicito_gana_sobre_el_entorno(monkeypatch):
    monkeypatch.setenv("NEXUS_EMBEDDING_MODEL", "del-entorno")
    assert cs.resolve_embedding_model("explicito") == "explicito"


# ── get_embedding_function ────────────────────────────────────────

def test_usa_el_modelo_pedido_cuando_hay_sentence_transformers(
    con_sentence_transformers, monkeypatch
):
    monkeypatch.delenv("NEXUS_EMBEDDING_MODEL", raising=False)
    _, efectivo = cs.get_embedding_function()
    assert efectivo == cs.BIOMEDICAL_EMBEDDING_MODEL


def test_cae_al_fallback_sin_sentence_transformers(
    sin_sentence_transformers, monkeypatch, capsys
):
    monkeypatch.delenv("NEXUS_EMBEDDING_MODEL", raising=False)
    _, efectivo = cs.get_embedding_function()

    assert efectivo == cs.FALLBACK_EMBEDDING_MODEL
    # El fallback avisa: nunca en silencio (regla del proyecto)
    assert "sentence-transformers no está instalado" in capsys.readouterr().err


def test_el_modelo_fallback_no_necesita_sentence_transformers(
    sin_sentence_transformers,
):
    """Pedir MiniLM explícitamente usa el ONNX de ChromaDB, sin warning."""
    _, efectivo = cs.get_embedding_function(cs.FALLBACK_EMBEDDING_MODEL)
    assert efectivo == cs.FALLBACK_EMBEDDING_MODEL


# ── Guarda de mismatch ───────────────────────────────────────────

def test_mismatch_de_modelo_levanta_excepcion(monkeypatch, nombre):
    """
    Una colección indexada con un modelo no se puede reusar con otro: los
    vectores no son comparables. Debe fallar explícito, no devolver basura.
    """
    client = chromadb.EphemeralClient()

    monkeypatch.setattr(
        cs, "get_embedding_function",
        lambda model_name=None: (_StubEmbeddingFunction(), "modelo-A"),
    )
    cs.get_pubmed_collection(client, collection_name=nombre)

    monkeypatch.setattr(
        cs, "get_embedding_function",
        lambda model_name=None: (_StubEmbeddingFunction(), "modelo-B"),
    )
    with pytest.raises(cs.EmbeddingModelMismatch) as exc:
        cs.get_pubmed_collection(client, collection_name=nombre)

    mensaje = str(exc.value)
    assert "modelo-A" in mensaje and "modelo-B" in mensaje
    assert "reset_collection" in mensaje  # el mensaje dice cómo salir


def test_mismo_modelo_reusa_la_coleccion(monkeypatch, nombre):
    client = chromadb.EphemeralClient()
    monkeypatch.setattr(
        cs, "get_embedding_function",
        lambda model_name=None: (_StubEmbeddingFunction(), "modelo-A"),
    )

    primera = cs.get_pubmed_collection(client, collection_name=nombre)
    segunda = cs.get_pubmed_collection(client, collection_name=nombre)
    assert primera.name == segunda.name


def test_collection_name_permite_modelos_en_paralelo(monkeypatch, nombre):
    """Dos modelos pueden coexistir en colecciones distintas (para comparar)."""
    client = chromadb.EphemeralClient()

    monkeypatch.setattr(
        cs, "get_embedding_function",
        lambda model_name=None: (_StubEmbeddingFunction(), "modelo-A"),
    )
    a = cs.get_pubmed_collection(client, collection_name=nombre + "_a")

    monkeypatch.setattr(
        cs, "get_embedding_function",
        lambda model_name=None: (_StubEmbeddingFunction(), "modelo-B"),
    )
    b = cs.get_pubmed_collection(client, collection_name=nombre + "_b")

    assert a.name != b.name
    assert cs.get_collection_stats(a)["embedding_model"] == "modelo-A"
    assert cs.get_collection_stats(b)["embedding_model"] == "modelo-B"


# ── reset_collection ─────────────────────────────────────────────

def test_reset_permite_cambiar_de_modelo(monkeypatch, nombre):
    """Tras un mismatch, reset_collection es la salida documentada."""
    client = chromadb.EphemeralClient()

    monkeypatch.setattr(
        cs, "get_embedding_function",
        lambda model_name=None: (_StubEmbeddingFunction(), "modelo-A"),
    )
    cs.get_pubmed_collection(client, collection_name=nombre)

    monkeypatch.setattr(
        cs, "get_embedding_function",
        lambda model_name=None: (_StubEmbeddingFunction(), "modelo-B"),
    )
    nueva = cs.reset_collection(client, collection_name=nombre)
    assert cs.get_collection_stats(nueva)["embedding_model"] == "modelo-B"


# ── Metadata de la colección ─────────────────────────────────────

def test_la_coleccion_registra_modelo_y_espacio_coseno(monkeypatch, nombre):
    client = chromadb.EphemeralClient()
    monkeypatch.setattr(
        cs, "get_embedding_function",
        lambda model_name=None: (_StubEmbeddingFunction(), "modelo-A"),
    )
    col = cs.get_pubmed_collection(client, collection_name=nombre)

    assert col.metadata["embedding_model"] == "modelo-A"
    assert col.metadata["hnsw:space"] == "cosine"


def test_stats_incluye_el_modelo(monkeypatch, nombre):
    client = chromadb.EphemeralClient()
    monkeypatch.setattr(
        cs, "get_embedding_function",
        lambda model_name=None: (_StubEmbeddingFunction(), "modelo-A"),
    )
    stats = cs.get_collection_stats(cs.get_pubmed_collection(client, collection_name=nombre))

    assert stats["count"] == 0
    assert stats["embedding_model"] == "modelo-A"
    assert stats["name"] == nombre
