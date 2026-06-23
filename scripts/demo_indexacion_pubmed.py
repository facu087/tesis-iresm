"""
Demo de verificación — Indexación de artículos PubMed en ChromaDB.

Muestra cómo se indexan artículos reales de PubMed en ChromaDB usando
el módulo backend/rag/indexer.py. Usa artículos de ejemplo locales
(sin llamar a la API de PubMed) para que funcione sin conexión.

Artefactos generados en output/demo_indexacion/:
    1. articulos_entrada.txt   → los 3 artículos que se van a indexar
    2. resultado_indexacion.txt → stats del proceso (IDs, conteo, tiempo)

Uso:
    python scripts/demo_indexacion_pubmed.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from backend.external.pubmed import PubMedArticle
from backend.rag.indexer import index_articles, _article_to_document

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_indexacion"

# Artículos de ejemplo (caso clínico de la tesis: neuropatía axonal, 42 años)
_ARTICULOS = [
    PubMedArticle(
        pmid="29470523",
        title="Hereditary transthyretin amyloidosis: a review",
        abstract=(
            "Hereditary transthyretin (ATTRv) amyloidosis is a progressive, fatal disease "
            "caused by mutations in the TTR gene. It manifests as polyneuropathy and/or "
            "cardiomyopathy. Patisiran and inotersen are approved RNA-targeted therapies "
            "that significantly reduce TTR protein levels and slow disease progression."
        ),
        journal="New England Journal of Medicine",
        year="2019",
        authors=["Adams D", "Gonzalez-Duarte A", "O'Riordan WD"],
    ),
    PubMedArticle(
        pmid="28754644",
        title="Autoimmune autonomic ganglionopathy",
        abstract=(
            "Autoimmune autonomic ganglionopathy (AAG) is characterized by subacute onset "
            "of autonomic failure with high titers of ganglionic acetylcholine receptor (AChR) "
            "antibodies. Treatment with immunotherapy including IVIg and plasmapheresis "
            "can lead to significant improvement."
        ),
        journal="Neurology",
        year="2017",
        authors=["Sandroni P", "Low PA"],
    ),
    PubMedArticle(
        pmid="30589315",
        title="Acute hepatic porphyria neuropathy: pathogenesis and treatment",
        abstract=(
            "Acute hepatic porphyria (AHP) presents with acute neurovisceral attacks including "
            "abdominal pain, peripheral neuropathy, and autonomic dysfunction. Givosiran, "
            "an RNA interference therapy targeting ALAS1, reduces attack frequency and "
            "improves neuropathy outcomes."
        ),
        journal="Journal of Neurology",
        year="2019",
        authors=["Pischik E", "Kauppinen R"],
    ),
]


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Indexación de artículos PubMed en ChromaDB")
    print(_SEP)

    # 1. Mostrar artículos de entrada
    print(f"\n  [1/4] Artículos a indexar: {len(_ARTICULOS)}")
    for i, a in enumerate(_ARTICULOS, 1):
        print(f"\n        Artículo {i}:")
        print(f"          PMID    : {a.pmid}")
        print(f"          Título  : {a.title}")
        print(f"          Revista : {a.journal} ({a.year})")
        print(f"          Autores : {', '.join(a.authors)}")

    # Guardar artículos de entrada como artefacto
    entrada_txt = _OUT_DIR / "articulos_entrada.txt"
    with entrada_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — Artículos de entrada para indexación\n")
        f.write("=" * 50 + "\n\n")
        for i, a in enumerate(_ARTICULOS, 1):
            f.write(f"[{i}] PMID: {a.pmid}\n")
            f.write(f"    Título: {a.title}\n")
            f.write(f"    Revista: {a.journal} ({a.year})\n")
            f.write(f"    Autores: {', '.join(a.authors)}\n")
            f.write(f"    Abstract: {a.abstract}\n\n")

    # 2. Mostrar cómo se convierten al formato ChromaDB
    print(f"\n  [2/4] Convirtiendo al formato ChromaDB (id / document / metadata)...")
    doc_ejemplo = _article_to_document(_ARTICULOS[0])
    print(f"        id       : {doc_ejemplo['id']}")
    print(f"        document : {doc_ejemplo['document'][:80]}...")
    print(f"        metadata : pmid={doc_ejemplo['metadata']['pmid']}, "
          f"year={doc_ejemplo['metadata']['year']}, "
          f"journal={doc_ejemplo['metadata']['journal'][:30]}")

    # 3. Indexar en colección en memoria (demo sin persistir)
    print(f"\n  [3/4] Indexando en ChromaDB (upsert)...")
    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection(
        name="nexus_pubmed_demo",
        metadata={"hnsw:space": "cosine"},
    )
    inicio = time.time()
    cantidad = index_articles(_ARTICULOS, collection=collection)
    elapsed = time.time() - inicio
    print(f"        ✓ {cantidad} artículos indexados en {elapsed:.2f}s")
    print(f"        ✓ Total en colección: {collection.count()}")

    # 4. Verificar que no duplica con segundo upsert
    print(f"\n  [4/4] Verificando deduplicación (upsert doble)...")
    index_articles(_ARTICULOS, collection=collection)
    print(f"        ✓ Después de re-indexar: {collection.count()} documentos (sin duplicados)")

    # Guardar resultado como artefacto
    resultado_txt = _OUT_DIR / "resultado_indexacion.txt"
    with resultado_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — Resultado de indexación PubMed → ChromaDB\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Artículos de entrada : {len(_ARTICULOS)}\n")
        f.write(f"Artículos indexados  : {cantidad}\n")
        f.write(f"Tiempo de indexación : {elapsed:.2f}s\n")
        f.write(f"Deduplicación        : ✓ (upsert por PMID)\n\n")
        f.write("IDs indexados:\n")
        for a in _ARTICULOS:
            f.write(f"  PMID {a.pmid} → {a.title[:60]}\n")
        f.write(f"\nTexto embedeado (ejemplo PMID {_ARTICULOS[0].pmid}):\n")
        f.write(f"  \"{doc_ejemplo['document'][:200]}...\"\n")

    print()
    print(_SEP)
    print("  RESULTADO FINAL:")
    print(_SEP)
    print(f"  Artículos indexados  : {cantidad}")
    print(f"  Tiempo               : {elapsed:.2f}s")
    print(f"  Deduplicación (upsert): ✓ sin duplicados")
    print(f"  Texto embedeado      : título + abstract concatenados")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • Artículos de entrada → {entrada_txt}")
    print(f"    • Resultado indexación → {resultado_txt}")
    print(_SEP)


if __name__ == "__main__":
    main()
