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
