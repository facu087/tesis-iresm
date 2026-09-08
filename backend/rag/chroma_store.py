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

Modelo de embeddings
--------------------
La query es una narrativa clínica (síntesis PICO del caso) y los documentos son
títulos + abstracts de PubMed en inglés. Por eso el default es un modelo del
dominio biomédico (PubMedBERT) afinado para embeddings de oraciones, y no el
modelo de dominio general que trae ChromaDB.

Se puede sobreescribir con la variable de entorno `NEXUS_EMBEDDING_MODEL` para
comparar modelos sin tocar código:

    NEXUS_EMBEDDING_MODEL=all-MiniLM-L6-v2 python3 scripts/demo_motor_rag.py

Ver `scripts/demo_embeddings_comparacion.py` para una comparación medida entre
el modelo biomédico y el general sobre el caso de prueba del proyecto.

Nota sobre SciBERT: `allenai/scibert_scivocab_uncased` es un modelo de lenguaje
enmascarado, NO un modelo de embeddings de oraciones. Sacarle vectores por
mean-pooling sin fine-tuning contrastivo rinde peor en similitud semántica que
un modelo entrenado para la tarea (Reimers & Gurevych, 2019). Por eso no se usa
acá, aunque el dominio sea el correcto.

Limitación conocida (de ambos modelos, medida): ningún modelo de embeddings
maneja la negación. Con la query del caso, que dice "negative CMT panel", los
dos traen Charcot-Marie-Tooth entre los primeros puestos. El hallazgo negativo
viaja igual en el prompt del agente (`negative_findings` de la síntesis PICO),
así que el agente puede razonar sobre él, pero el recuperador no lo usa para
filtrar.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional

import chromadb
from chromadb.config import Settings

# Directorio de persistencia local
_CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")
_COLLECTION_NAME = "nexus_pubmed"

# Modelo por defecto: PubMedBERT afinado para embeddings de oraciones.
# 768 dimensiones. Requiere `sentence-transformers` instalado.
#
# Se eligió MIDIENDO (scripts/demo_embeddings_comparacion.py) sobre el caso de
# prueba. Se descartó `pritamdeka/S-PubMedBert-MS-MARCO`: ordena razonablemente
# pero sus scores quedan comprimidos entre 0.951 y 0.980 —amplitud 0.029— así
# que el `relevance_score` deja de ser informativo y el umbral del retriever se
# vuelve imposible de calibrar. Es el comportamiento típico de los modelos
# entrenados sobre MS MARCO: optimizan el orden, no la calibración del score.
BIOMEDICAL_EMBEDDING_MODEL = "NeuML/pubmedbert-base-embeddings"

# Modelo de fallback: el default de ChromaDB (MiniLM vía ONNX, 384 dimensiones).
# No requiere torch ni sentence-transformers. Es de dominio general.
FALLBACK_EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Variable de entorno para sobreescribir el modelo sin tocar código.
_ENV_MODEL_VAR = "NEXUS_EMBEDDING_MODEL"


def resolve_embedding_model(model_name: Optional[str] = None) -> str:
    """
    Determina qué modelo de embeddings usar.

    Precedencia: argumento explícito > variable de entorno > default biomédico.

    Args:
        model_name: Nombre del modelo. Si es None, se consulta el entorno.

    Returns:
        Nombre del modelo a usar.
    """
    if model_name:
        return model_name
    return os.environ.get(_ENV_MODEL_VAR) or BIOMEDICAL_EMBEDDING_MODEL


def get_embedding_function(model_name: Optional[str] = None) -> tuple[Any, str]:
    """
    Construye la función de embedding para la colección.

    Si el modelo pedido es el default de ChromaDB, usa su implementación ONNX
    (sin dependencias extra). Para cualquier otro modelo usa
    sentence-transformers.

    Fallback explícito: si `sentence-transformers` no está instalado, avisa por
    stderr y cae al modelo default de ChromaDB. Nunca falla en silencio ni
    deja la colección sin función de embedding.

    Args:
        model_name: Modelo a usar. Si es None, se resuelve con
                    `resolve_embedding_model()`.

    Returns:
        Tupla (embedding_function, nombre_efectivo_del_modelo). El nombre
        efectivo puede diferir del pedido si hubo fallback.
    """
    from chromadb.utils import embedding_functions

    requested = resolve_embedding_model(model_name)

    if requested == FALLBACK_EMBEDDING_MODEL:
        return embedding_functions.DefaultEmbeddingFunction(), FALLBACK_EMBEDDING_MODEL

    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        print(
            f"[NEXUS] sentence-transformers no está instalado: no se puede usar "
            f"'{requested}'. Cayendo a '{FALLBACK_EMBEDDING_MODEL}' (modelo general, "
            f"384 dims). Para usar el modelo biomédico: "
            f"pip install -r backend/requirements.txt",
            file=sys.stderr,
        )
        return embedding_functions.DefaultEmbeddingFunction(), FALLBACK_EMBEDDING_MODEL

    return (
        embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=requested,
            device="cpu",
            normalize_embeddings=True,  # coherente con hnsw:space=cosine
        ),
        requested,
    )


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


class EmbeddingModelMismatch(RuntimeError):
    """
    La colección en disco fue construida con otro modelo de embeddings.

    Los vectores de dos modelos distintos no son comparables (y pueden ni
    coincidir en dimensión), así que reusar la colección daría resultados
    de similitud sin sentido. Hay que re-indexar.
    """


def get_pubmed_collection(
    client: Optional[chromadb.PersistentClient] = None,
    model_name: Optional[str] = None,
    collection_name: Optional[str] = None,
) -> chromadb.Collection:
    """
    Obtiene o crea la colección de artículos PubMed en ChromaDB.

    La colección guarda en su metadata el modelo con el que fue construida. Si
    ya existe y fue construida con otro modelo, se levanta
    `EmbeddingModelMismatch` en vez de devolver una colección cuyos vectores no
    son comparables con los nuevos.

    Args:
        client:          Cliente ChromaDB opcional. Si no se pasa, crea uno nuevo.
        model_name:      Modelo de embeddings. Si es None, se resuelve del entorno.
        collection_name: Nombre de colección alternativo. Útil para comparar
                         modelos en paralelo sin pisar la colección principal.

    Returns:
        chromadb.Collection lista para usar.

    Raises:
        EmbeddingModelMismatch: si la colección existente usa otro modelo.
    """
    if client is None:
        client = get_chroma_client()

    embedding_fn, effective_model = get_embedding_function(model_name)
    name = collection_name or _COLLECTION_NAME

    # Metadata de las colecciones existentes. `list_collections()` la expone sin
    # necesitar la función de embedding, así que se puede validar el modelo
    # ANTES de intentar abrir la colección. Se evita así envolver el
    # get_collection en un try/except que taparía errores reales (y que hacía
    # caer el create_collection de abajo con "already exists").
    existing_metadata = {
        col.name: (col.metadata or {}) for col in client.list_collections()
    }

    if name in existing_metadata:
        stored = existing_metadata[name].get("embedding_model")
        if stored and stored != effective_model:
            raise EmbeddingModelMismatch(
                f"La colección '{name}' fue indexada con '{stored}' y ahora se pide "
                f"'{effective_model}'. Los vectores no son comparables.\n"
                f"Opciones:\n"
                f"  1. Re-indexar desde cero: reset_collection(model_name='{effective_model}')\n"
                f"  2. Seguir con el modelo original: "
                f"{_ENV_MODEL_VAR}='{stored}'\n"
                f"  3. Usar otra colección: get_pubmed_collection(collection_name='...')"
            )
        return client.get_collection(name=name, embedding_function=embedding_fn)

    return client.create_collection(
        name=name,
        embedding_function=embedding_fn,
        metadata={
            "description": "Artículos PubMed indexados para RAG en NEXUS",
            "embedding_model": effective_model,
            "hnsw:space": "cosine",  # Distancia coseno para similitud semántica
        },
    )


def get_collection_stats(collection: chromadb.Collection) -> dict:
    """
    Devuelve estadísticas básicas de la colección.

    Args:
        collection: Colección ChromaDB

    Returns:
        Dict con nombre, cantidad de documentos y modelo de embeddings usado.
    """
    return {
        "name": collection.name,
        "count": collection.count(),
        "embedding_model": (collection.metadata or {}).get("embedding_model", "desconocido"),
    }


def reset_collection(
    client: Optional[chromadb.PersistentClient] = None,
    model_name: Optional[str] = None,
    collection_name: Optional[str] = None,
) -> chromadb.Collection:
    """
    Borra y recrea la colección (útil para re-indexar desde cero).

    Es también la salida cuando se cambia de modelo de embeddings y
    `get_pubmed_collection()` levanta `EmbeddingModelMismatch`.

    Args:
        client:          Cliente ChromaDB opcional
        model_name:      Modelo de embeddings para la colección nueva
        collection_name: Nombre de colección alternativo

    Returns:
        Nueva colección vacía
    """
    if client is None:
        client = get_chroma_client()

    name = collection_name or _COLLECTION_NAME

    try:
        client.delete_collection(name)
    except Exception:
        pass  # No existía — ignorar

    return get_pubmed_collection(
        client, model_name=model_name, collection_name=collection_name
    )
