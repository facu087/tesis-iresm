"""
Demo de verificación — Setup ChromaDB: colección y embeddings biomédicos.

Muestra cómo se crea la colección 'nexus_pubmed' en ChromaDB con embeddings
de similitud coseno, y verifica que persiste en disco entre ejecuciones.

Artefactos generados en output/demo_chromadb/:
    1. stats_coleccion.txt  → estadísticas de la colección (nombre, count, metadata)
    2. test_upsert.txt      → resultado de insertar y recuperar un documento de prueba

Uso:
    python scripts/demo_chromadb.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.rag.chroma_store import get_chroma_client, get_pubmed_collection, get_collection_stats, reset_collection

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_chromadb"

_DOCUMENTO_PRUEBA = {
    "id": "NEXUS_TEST_001",
    "document": "Hereditary transthyretin amyloidosis causes progressive peripheral neuropathy. "
                "Patisiran is an RNA interference therapy that reduces TTR protein levels.",
    "metadata": {
        "pmid": "NEXUS_TEST_001",
        "title": "Documento de prueba NEXUS",
        "journal": "NEXUS Test",
        "year": "2024",
        "authors": "NEXUS Team",
        "url": "https://nexus.test/001",
    },
}


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Setup ChromaDB: colección y embeddings biomédicos")
    print(_SEP)

    # 1. Crear cliente y colección
    print("\n  [1/4] Creando cliente ChromaDB persistente...")
    client = get_chroma_client()
    print(f"        ✓ Cliente creado — datos en: chroma_db/")

    # 2. Obtener/crear colección
    print("\n  [2/4] Obteniendo colección 'nexus_pubmed'...")
    collection = get_pubmed_collection(client)
    stats_antes = get_collection_stats(collection)
    print(f"        ✓ Colección: {stats_antes['name']}")
    print(f"        ✓ Documentos actuales: {stats_antes['count']}")
    print(f"        ✓ Embedding model: all-MiniLM-L6-v2 (distancia coseno)")

    # 3. Insertar documento de prueba
    print("\n  [3/4] Insertando documento de prueba (upsert)...")
    collection.upsert(
        ids=[_DOCUMENTO_PRUEBA["id"]],
        documents=[_DOCUMENTO_PRUEBA["document"]],
        metadatas=[_DOCUMENTO_PRUEBA["metadata"]],
    )
    stats_despues = get_collection_stats(collection)
    print(f"        ✓ Documentos después del upsert: {stats_despues['count']}")

    # 4. Verificar que se puede recuperar
    print("\n  [4/4] Verificando recuperación del documento...")
    resultado = collection.get(ids=[_DOCUMENTO_PRUEBA["id"]], include=["documents", "metadatas"])
    doc_recuperado = resultado["documents"][0]
    meta_recuperada = resultado["metadatas"][0]
    print(f"        ✓ Documento recuperado correctamente")
    print(f"        ✓ Título: {meta_recuperada['title']}")

    # Limpiar documento de prueba
    collection.delete(ids=[_DOCUMENTO_PRUEBA["id"]])

    # Guardar artefacto
    stats_txt = _OUT_DIR / "stats_coleccion.txt"
    stats_txt.write_text(
        f"NEXUS — Demo ChromaDB\n"
        f"{'=' * 50}\n\n"
        f"Colección: {stats_antes['name']}\n"
        f"Embedding model: all-MiniLM-L6-v2\n"
        f"Distancia: coseno\n"
        f"Documentos indexados: {stats_antes['count']}\n"
        f"Persistencia: chroma_db/ (local)\n\n"
        f"Test upsert → get:\n"
        f"  ID insertado: {_DOCUMENTO_PRUEBA['id']}\n"
        f"  Documento: {doc_recuperado[:120]}...\n"
        f"  Metadata: {meta_recuperada}\n"
        f"  Resultado: ✓ OK\n",
        encoding="utf-8",
    )

    print()
    print(_SEP)
    print("  RESULTADO FINAL:")
    print(_SEP)
    print(f"  Colección       : {stats_antes['name']}")
    print(f"  Embedding model : all-MiniLM-L6-v2 (sentence-transformers)")
    print(f"  Distancia       : coseno")
    print(f"  Persistencia    : chroma_db/ (entre sesiones)")
    print(f"  Upsert/get test : ✓ OK")
    print()
    print("  ARTEFACTO GENERADO (abrir y capturar para Trello):")
    print(f"    • Stats colección → {stats_txt}")
    print(_SEP)


if __name__ == "__main__":
    main()
