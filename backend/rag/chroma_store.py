"""
Setup de ChromaDB: colección y embeddings biomédicos.

ChromaDB es la base de datos vectorial local que almacena artículos de PubMed
como embeddings. Permite búsqueda semántica por similitud para enriquecer
el contexto de los agentes con literatura científica real.

Colección principal: "nexus_pubmed"
  - Cada documento = un artículo de PubMed
  - Embedding = título + abstract concatenados
  - Metadata: pmid, title, journal, year, authors, url

Persistencia: ./chroma_db/ (ignorado por git — datos locales de sesión)
"""

from __future__ import annotations

import os
from typing import Optional

import chromadb
from chromadb.config import Settings

# Directorio de persistencia local
_CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")
_COLLECTION_NAME = "nexus_pubmed"

# Función de embedding: por defecto ChromaDB usa all-MiniLM-L6-v2 (sentence-transformers)
# Es un modelo liviano y suficientemente bueno para literatura biomédica en inglés.
# Si se quiere más precisión: cambiar a "paraphrase-multilingual-MiniLM-L12-v2" para español.
_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def get_chroma_client() -> chromadb.PersistentClient:
    """
    Crea o reutiliza el cliente ChromaDB persistente.

    Returns:
        chromadb.PersistentClient apuntando a ./chroma_db/
    """
    os.makedirs(_CHROMA_PATH, exist_ok=True)
    return chromadb.PersistentClient(
        path=_CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )


def get_pubmed_collection(
    client: Optional[chromadb.PersistentClient] = None,
) -> chromadb.Collection:
    """
    Obtiene o crea la colección 'nexus_pubmed' en ChromaDB.

    Usa embeddings de sentence-transformers (all-MiniLM-L6-v2).
    La colección persiste en disco entre sesiones.

    Args:
        client: Cliente ChromaDB opcional. Si no se pasa, crea uno nuevo.

    Returns:
        chromadb.Collection lista para usar
    """
    if client is None:
        client = get_chroma_client()

    collection = client.get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={
            "description": "Artículos PubMed indexados para RAG en NEXUS",
            "embedding_model": _EMBEDDING_MODEL,
            "hnsw:space": "cosine",  # Distancia coseno para similitud semántica
        },
    )
    return collection


def get_collection_stats(collection: chromadb.Collection) -> dict:
    """
    Devuelve estadísticas básicas de la colección.

    Args:
        collection: Colección ChromaDB

    Returns:
        Dict con count y nombre
    """
    return {
        "name": collection.name,
        "count": collection.count(),
    }


def reset_collection(
    client: Optional[chromadb.PersistentClient] = None,
) -> chromadb.Collection:
    """
    Borra y recrea la colección (útil para re-indexar desde cero).

    Args:
        client: Cliente ChromaDB opcional

    Returns:
        Nueva colección vacía
    """
    if client is None:
        client = get_chroma_client()

    try:
        client.delete_collection(_COLLECTION_NAME)
    except Exception:
        pass  # No existía — ignorar

    return get_pubmed_collection(client)
