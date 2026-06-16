"""
Indexación de artículos PubMed en ChromaDB.

Este módulo toma artículos de PubMed (PubMedArticle) y los almacena
como vectores en ChromaDB para búsqueda semántica posterior.

Estrategia de indexación:
  - Texto a embedear: "{title}. {abstract}" (concatenado)
  - ID del documento: pmid (único en PubMed)
  - Metadata: pmid, title, journal, year, authors_str, url
  - Deduplicación: si el PMID ya existe, se omite (upsert silencioso)
"""

from __future__ import annotations

from typing import Optional

import chromadb

from backend.external.pubmed import PubMedArticle, PubMedClient
from backend.rag.chroma_store import get_pubmed_collection


def _article_to_document(article: PubMedArticle) -> dict:
    """
    Convierte un PubMedArticle al formato que espera ChromaDB.

    Args:
        article: Artículo de PubMed

    Returns:
        Dict con 'id', 'document', 'metadata'
    """
    text = f"{article.title}. {article.abstract}".strip()
    return {
        "id": article.pmid,
        "document": text,
        "metadata": {
            "pmid": article.pmid,
            "title": article.title,
            "journal": article.journal,
            "year": article.year,
            "authors": ", ".join(article.authors[:5]),
            "url": article.url,
        },
    }


def index_articles(
    articles: list[PubMedArticle],
    collection: Optional[chromadb.Collection] = None,
) -> int:
    """
    Indexa una lista de artículos en ChromaDB.

    Usa upsert para evitar duplicados: si el PMID ya existe, actualiza.

    Args:
        articles: Lista de PubMedArticle a indexar
        collection: Colección ChromaDB opcional. Si no se pasa, usa la default.

    Returns:
        Cantidad de artículos indexados
    """
    if not articles:
        return 0

    if collection is None:
        collection = get_pubmed_collection()

    docs = [_article_to_document(a) for a in articles]

    collection.upsert(
        ids=[d["id"] for d in docs],
        documents=[d["document"] for d in docs],
        metadatas=[d["metadata"] for d in docs],
    )

    return len(docs)


async def index_from_query(
    query: str,
    max_articles: int = 10,
    collection: Optional[chromadb.Collection] = None,
) -> int:
    """
    Busca artículos en PubMed por query y los indexa en ChromaDB.

    Combina la búsqueda en PubMed con la indexación en un solo paso.
    Útil para pre-cargar la base de conocimiento antes de un análisis.

    Args:
        query: Query PubMed (ej: "TTR amyloidosis neuropathy treatment")
        max_articles: Máximo de artículos a buscar y guardar
        collection: Colección ChromaDB opcional

    Returns:
        Cantidad de artículos indexados
    """
    async with PubMedClient() as client:
        articles = await client.search(query, max_results=max_articles)

    if not articles:
        return 0

    return index_articles(articles, collection)


async def index_from_clinical_context(
    genes: list[str],
    conditions: list[str],
    drugs: list[str],
    collection: Optional[chromadb.Collection] = None,
) -> dict[str, int]:
    """
    Indexa literatura relevante para un caso clínico específico.

    Construye múltiples queries a partir del contexto del caso y las
    ejecuta en paralelo para cubrir genes, condiciones y fármacos.

    Args:
        genes: Lista de genes del caso (ej: ["TTR", "ATTR"])
        conditions: Lista de condiciones/diagnósticos del caso
        drugs: Lista de fármacos actuales del paciente
        collection: Colección ChromaDB opcional

    Returns:
        Dict {query: artículos_indexados}
    """
    import asyncio

    if collection is None:
        collection = get_pubmed_collection()

    # Construir queries específicas para el caso
    queries: list[str] = []

    for gene in genes[:3]:  # Limitar para no saturar la API
        queries.append(f"{gene} mutation neuropathy treatment")

    for condition in conditions[:2]:
        queries.append(f"{condition} clinical management evidence")

    for drug in drugs[:2]:
        queries.append(f"{drug} efficacy safety neuropathy")

    if not queries:
        return {}

    # Ejecutar todas las búsquedas en paralelo
    results = await asyncio.gather(
        *[index_from_query(q, max_articles=5, collection=collection) for q in queries],
        return_exceptions=True,
    )

    return {
        query: count if isinstance(count, int) else 0
        for query, count in zip(queries, results)
    }
