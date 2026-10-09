"""
Tests para el módulo RAG (ChromaDB + indexer + retriever).

Usa colecciones en memoria (no persisten en disco) para no contaminar
la base de datos local durante los tests.
"""

import pytest
import chromadb

from backend.external.pubmed import PubMedArticle
from backend.rag.chroma_store import get_pubmed_collection, get_collection_stats, reset_collection
from backend.rag.indexer import index_articles, _article_to_document
from backend.rag.retriever import PubMedRetriever, RetrievedArticle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_collection_counter = 0

@pytest.fixture
def in_memory_collection():
    """Colección ChromaDB en memoria para tests (no persiste en disco)."""
    global _collection_counter
    _collection_counter += 1
    client = chromadb.EphemeralClient()
    return client.get_or_create_collection(
        name=f"test_collection_{_collection_counter}",
        metadata={"hnsw:space": "cosine"},
    )


@pytest.fixture
def sample_articles() -> list[PubMedArticle]:
    return [
        PubMedArticle(
            pmid="29470523",
            title="Hereditary transthyretin amyloidosis: a review",
            abstract="TTR amyloidosis causes progressive peripheral neuropathy. Patisiran reduces TTR protein.",
            journal="N Engl J Med",
            year="2019",
            authors=["Adams D", "Gonzalez-Duarte A"],
        ),
        PubMedArticle(
            pmid="28754644",
            title="Autoimmune autonomic ganglionopathy",
            abstract="AAG is characterized by subacute autonomic failure with ganglionic AChR antibodies.",
            journal="Neurology",
            year="2017",
            authors=["Sandroni P"],
        ),
        PubMedArticle(
            pmid="30589315",
            title="Acute hepatic porphyria neuropathy",
            abstract="Porphyria presents with acute attacks, neuropathy and abdominal pain.",
            journal="J Neurol",
            year="2019",
            authors=["Pischik E", "Kauppinen R"],
        ),
    ]


# ---------------------------------------------------------------------------
# Tests: _article_to_document
# ---------------------------------------------------------------------------

class TestArticleToDocument:
    def test_concatena_titulo_y_abstract(self, sample_articles):
        doc = _article_to_document(sample_articles[0])
        assert "Hereditary transthyretin" in doc["document"]
        assert "Patisiran" in doc["document"]

    def test_id_es_pmid(self, sample_articles):
        doc = _article_to_document(sample_articles[0])
        assert doc["id"] == "29470523"

    def test_metadata_contiene_campos_clave(self, sample_articles):
        doc = _article_to_document(sample_articles[0])
        meta = doc["metadata"]
        assert meta["pmid"] == "29470523"
        assert meta["journal"] == "N Engl J Med"
        assert meta["year"] == "2019"
        assert "Adams D" in meta["authors"]
        assert "pubmed.ncbi.nlm.nih.gov" in meta["url"]


# ---------------------------------------------------------------------------
# Tests: index_articles
# ---------------------------------------------------------------------------

class TestIndexArticles:
    def test_indexa_articulos_correctamente(self, in_memory_collection, sample_articles):
        count = index_articles(sample_articles, collection=in_memory_collection)
        assert count == 3
        assert in_memory_collection.count() == 3

    def test_lista_vacia_devuelve_cero(self, in_memory_collection):
        count = index_articles([], collection=in_memory_collection)
        assert count == 0

    def test_upsert_no_duplica(self, in_memory_collection, sample_articles):
        index_articles(sample_articles, collection=in_memory_collection)
        index_articles(sample_articles, collection=in_memory_collection)
        assert in_memory_collection.count() == 3  # No duplicó


# ---------------------------------------------------------------------------
# Tests: get_collection_stats
# ---------------------------------------------------------------------------

def test_get_collection_stats(in_memory_collection, sample_articles):
    index_articles(sample_articles, collection=in_memory_collection)
    stats = get_collection_stats(in_memory_collection)
    assert stats["count"] == 3
    assert "test_collection" in stats["name"]


# ---------------------------------------------------------------------------
# Tests: PubMedRetriever
# ---------------------------------------------------------------------------

class TestPubMedRetriever:
    def test_search_devuelve_resultados_relevantes(self, in_memory_collection, sample_articles):
        index_articles(sample_articles, collection=in_memory_collection)
        retriever = PubMedRetriever(collection=in_memory_collection)

        results = retriever.search("TTR amyloidosis neuropathy patisiran")
        assert len(results) > 0
        assert all(isinstance(r, RetrievedArticle) for r in results)
        # El artículo de TTR debe ser el más relevante
        assert results[0].pmid == "29470523"

    def test_search_coleccion_vacia_devuelve_lista_vacia(self, in_memory_collection):
        retriever = PubMedRetriever(collection=in_memory_collection)
        results = retriever.search("cualquier query")
        assert results == []

    def test_retrieved_article_tiene_score_valido(self, in_memory_collection, sample_articles):
        index_articles(sample_articles, collection=in_memory_collection)
        retriever = PubMedRetriever(collection=in_memory_collection)
        results = retriever.search("neuropathy", max_results=3)
        for r in results:
            assert 0.0 <= r.relevance_score <= 1.0

    def test_get_context_for_agent_con_articulos(self, in_memory_collection, sample_articles):
        index_articles(sample_articles, collection=in_memory_collection)
        retriever = PubMedRetriever(collection=in_memory_collection)
        context = retriever.get_context_for_agent("TTR amyloidosis")
        assert "PMID" in context
        assert "29470523" in context
        assert "INSTRUCCIÓN" in context

    def test_get_context_for_agent_sin_articulos_da_fallback(self, in_memory_collection):
        retriever = PubMedRetriever(collection=in_memory_collection)
        context = retriever.get_context_for_agent("cualquier query")
        assert "No se encontraron artículos" in context
        assert "evidence_level" in context

    def test_get_pmids_for_hypothesis(self, in_memory_collection, sample_articles):
        index_articles(sample_articles, collection=in_memory_collection)
        retriever = PubMedRetriever(collection=in_memory_collection)
        pmids = retriever.get_pmids_for_hypothesis(
            "Hereditary TTR amyloidosis causes neuropathy and patisiran is effective"
        )
        assert isinstance(pmids, list)
        assert all(isinstance(p, str) for p in pmids)

    def test_collection_size(self, in_memory_collection, sample_articles):
        retriever = PubMedRetriever(collection=in_memory_collection)
        assert retriever.collection_size() == 0
        index_articles(sample_articles, collection=in_memory_collection)
        assert retriever.collection_size() == 3


# ---------------------------------------------------------------------------
# Tests: RetrievedArticle
# ---------------------------------------------------------------------------

class TestRetrievedArticle:
    def test_to_citation(self):
        article = RetrievedArticle(
            pmid="29470523",
            title="TTR review",
            journal="N Engl J Med",
            year="2019",
            authors="Adams D, Gonzalez-Duarte A",
            url="https://pubmed.ncbi.nlm.nih.gov/29470523/",
            excerpt="TTR causes neuropathy.",
            relevance_score=0.85,
        )
        citation = article.to_citation()
        assert "29470523" in citation
        assert "TTR review" in citation
        assert "N Engl J Med" in citation

    def test_to_prompt_block(self):
        article = RetrievedArticle(
            pmid="29470523",
            title="TTR review",
            journal="N Engl J Med",
            year="2019",
            authors="Adams D",
            url="https://pubmed.ncbi.nlm.nih.gov/29470523/",
            excerpt="TTR causes neuropathy.",
            relevance_score=0.85,
        )
        block = article.to_prompt_block()
        assert "[PMID: 29470523]" in block
        assert "0.85" in block


# ---------------------------------------------------------------------------
# Umbral de relevancia (hallazgo A, tarjeta #76)
# ---------------------------------------------------------------------------

class _ColeccionFalsa:
    """
    Colección mínima con distancias controladas, para probar el filtro sin
    depender del modelo de embeddings ni de la red.
    """

    def __init__(self, distancias: list[float]) -> None:
        self._distancias = distancias

    def count(self) -> int:
        return len(self._distancias)

    def query(self, query_texts, n_results, include):
        n = min(n_results, len(self._distancias))
        return {
            "documents": [["doc"] * n],
            "metadatas": [[
                {"pmid": f"{i:08d}", "title": f"Articulo {i}", "journal": "J",
                 "year": "2024", "authors": "A"}
                for i in range(n)
            ]],
            "distances": [self._distancias[:n]],
        }


def _retriever_con(distancias: list[float]) -> PubMedRetriever:
    return PubMedRetriever(collection=_ColeccionFalsa(distancias))


class TestEscalaDelScore:
    """
    El score NO es la similitud coseno: es (1 + coseno) / 2, porque ChromaDB
    devuelve distancia coseno en [0, 2] y el retriever hace 1 - distancia/2.
    Confundir las dos escalas fue exactamente el hallazgo A.
    """

    @pytest.mark.parametrize("distancia,score_esperado,coseno", [
        (0.0, 1.0, 1.0),    # idéntico
        (1.0, 0.5, 0.0),    # ortogonal
        (2.0, 0.0, -1.0),   # opuesto
        (0.9, 0.55, 0.1),   # el umbral por defecto
    ])
    def test_conversion_distancia_a_score(self, distancia, score_esperado, coseno):
        articulos = _retriever_con([distancia]).search("q", min_score=0.0)
        assert articulos[0].relevance_score == pytest.approx(score_esperado, abs=1e-3)
        assert (1 + coseno) / 2 == pytest.approx(score_esperado, abs=1e-3)

    def test_el_umbral_viejo_no_filtraba_nada(self):
        """
        0.3 equivale a un coseno de -0,4. Ni un artículo ortogonal al query
        (coseno 0, lo más parecido a "sin relación" que hay) quedaba afuera.
        """
        ortogonal = 1.0
        assert _retriever_con([ortogonal]).search("q", min_score=0.3) != []
        assert _retriever_con([ortogonal]).search("q", min_score=0.55) == []


class TestFiltroDeRelevancia:
    def test_descarta_los_que_estan_por_debajo(self):
        # scores: 0.75, 0.60, 0.50, 0.40
        articulos = _retriever_con([0.5, 0.8, 1.0, 1.2]).search("q", max_results=10)
        assert [a.relevance_score for a in articulos] == [0.75, 0.6]

    def test_el_limite_es_inclusivo(self):
        """Un artículo justo en el umbral se conserva: la comparación es `<`."""
        assert _retriever_con([0.9]).search("q", min_score=0.55) != []

    def test_sin_resultados_relevantes_devuelve_vacio(self):
        assert _retriever_con([1.5, 1.8]).search("q") == []

    def test_get_pmids_for_hypothesis_usa_el_mismo_umbral(self):
        """Antes tenía un 0.35 propio, descrito como 'más alto' y más permisivo."""
        pmids = _retriever_con([0.5, 1.2]).get_pmids_for_hypothesis("hipotesis")
        assert len(pmids) == 1


class TestUmbralConfigurable:
    def test_default_medido(self):
        from backend.rag import retriever as r
        assert r._DEFAULT_MIN_RELEVANCE_SCORE == 0.55

    def test_toma_el_valor_del_entorno(self, monkeypatch):
        from backend.rag import retriever as r
        monkeypatch.setenv(r._ENV_MIN_SCORE_VAR, "0.7")
        assert r._resolver_min_score() == 0.7

    @pytest.mark.parametrize("valor", ["abc", "", "1.5", "-0.2"])
    def test_valor_invalido_cae_al_default_sin_romper(self, valor, monkeypatch, capsys):
        from backend.rag import retriever as r
        monkeypatch.setenv(r._ENV_MIN_SCORE_VAR, valor)
        assert r._resolver_min_score() == r._DEFAULT_MIN_RELEVANCE_SCORE
        if valor:  # el vacío se trata como "no configurado", sin aviso
            assert r._ENV_MIN_SCORE_VAR in capsys.readouterr().err
