"""
Demo de verificación — Motor RAG: búsqueda semántica y formateo para prompts.

Muestra el flujo completo del motor RAG:
  1. Se indexan artículos de PubMed en ChromaDB
  2. Se hace una búsqueda semántica con un query clínico real
  3. Se genera el contexto bibliográfico formateado para el prompt de un agente

Artefactos generados en output/demo_motor_rag/:
    1. query_y_resultados.txt   → query clínico + artículos recuperados con scores
    2. contexto_para_agente.txt → bloque de texto listo para pegar en un prompt de agente

Uso:
    python scripts/demo_motor_rag.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from backend.external.pubmed import PubMedArticle
from backend.rag.indexer import index_articles
from backend.rag.retriever import PubMedRetriever

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_motor_rag"

# Base de conocimiento: artículos relevantes para el caso clínico de la tesis
_ARTICULOS = [
    PubMedArticle(
        pmid="29470523",
        title="Hereditary transthyretin amyloidosis: a review",
        abstract=(
            "Hereditary transthyretin (ATTRv) amyloidosis is caused by mutations in the TTR gene. "
            "It manifests as progressive polyneuropathy and cardiomyopathy. "
            "Patisiran and inotersen are approved RNA-targeted therapies that reduce TTR levels."
        ),
        journal="New England Journal of Medicine",
        year="2019",
        authors=["Adams D", "Gonzalez-Duarte A"],
    ),
    PubMedArticle(
        pmid="28754644",
        title="Autoimmune autonomic ganglionopathy: diagnosis and treatment",
        abstract=(
            "AAG is characterized by subacute autonomic failure with ganglionic AChR antibodies. "
            "Immunotherapy with IVIg and plasmapheresis leads to significant improvement. "
            "Differential diagnosis includes hereditary neuropathies and paraneoplastic syndromes."
        ),
        journal="Neurology",
        year="2017",
        authors=["Sandroni P"],
    ),
    PubMedArticle(
        pmid="30589315",
        title="Acute hepatic porphyria neuropathy: pathogenesis and treatment",
        abstract=(
            "Acute hepatic porphyria presents with peripheral motor neuropathy and autonomic dysfunction. "
            "Givosiran reduces ALAS1 expression via RNA interference, decreasing attack frequency."
        ),
        journal="Journal of Neurology",
        year="2019",
        authors=["Pischik E", "Kauppinen R"],
    ),
    PubMedArticle(
        pmid="31504380",
        title="Diabetic peripheral neuropathy: diagnosis and management",
        abstract=(
            "Diabetic peripheral neuropathy affects up to 50% of patients with diabetes. "
            "HbA1c control is the primary prevention strategy. "
            "Axonal sensorimotor neuropathy is the most common subtype."
        ),
        journal="Lancet Neurology",
        year="2019",
        authors=["Feldman EL", "Nave KA", "Jensen TS"],
    ),
    PubMedArticle(
        pmid="27400955",
        title="Charcot-Marie-Tooth disease: update on genetics and pathogenesis",
        abstract=(
            "CMT is the most common inherited peripheral neuropathy. "
            "CMT1A is caused by PMP22 duplication; CMT2 subtypes involve axonal degeneration. "
            "Electrodiagnostic studies distinguish demyelinating from axonal forms."
        ),
        journal="Nature Reviews Neurology",
        year="2016",
        authors=["Rossor AM", "Polke JM", "Houlden H"],
    ),
]

# Query clínico real del caso de la tesis
_QUERY = "neuropatía axonal sensitivomotora progresiva en paciente masculino de 42 años con diabetes tipo 2 y panel CMT negativo"

# Hipótesis de ejemplo para buscar PMIDs de respaldo
_HIPOTESIS = "Posible amiloidosis hereditaria por TTR como causa de neuropatía axonal progresiva en paciente con antecedentes familiares"


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Motor RAG: búsqueda semántica y formateo para prompts")
    print(_SEP)

    # 1. Preparar colección en memoria con artículos de ejemplo
    print(f"\n  [1/5] Indexando {len(_ARTICULOS)} artículos de PubMed en ChromaDB...")
    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection(
        name="nexus_pubmed_demo",
        metadata={"hnsw:space": "cosine"},
    )
    index_articles(_ARTICULOS, collection=collection)
    print(f"        ✓ {collection.count()} artículos listos para búsqueda")

    retriever = PubMedRetriever(collection=collection)

    # 2. Búsqueda semántica con query clínico
    print(f"\n  [2/5] Búsqueda semántica con query clínico:")
    print(f"        \"{_QUERY[:80]}...\"")
    resultados = retriever.search(_QUERY, max_results=3)
    print(f"\n        Resultados (top {len(resultados)}):")
    for i, r in enumerate(resultados, 1):
        print(f"\n        [{i}] PMID: {r.pmid} — Score: {r.relevance_score:.3f}")
        print(f"            {r.title}")
        print(f"            {r.journal} ({r.year})")

    # 3. Generar contexto para agente
    print(f"\n  [3/5] Generando contexto bibliográfico para prompt de agente...")
    contexto = retriever.get_context_for_agent(_QUERY, max_results=3)
    lineas_contexto = contexto.count("\n")
    print(f"        ✓ Contexto generado: {len(contexto)} caracteres, {lineas_contexto} líneas")

    # 4. Buscar PMIDs para una hipótesis específica
    print(f"\n  [4/5] Buscando PMIDs para respaldar hipótesis:")
    print(f"        \"{_HIPOTESIS[:80]}...\"")
    pmids = retriever.get_pmids_for_hypothesis(_HIPOTESIS, max_results=2)
    print(f"        ✓ PMIDs reales encontrados: {pmids if pmids else 'ninguno con score suficiente'}")

    # 5. Guardar artefactos
    print(f"\n  [5/5] Guardando artefactos...")

    # Artefacto 1: query + resultados
    query_txt = _OUT_DIR / "query_y_resultados.txt"
    with query_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — Motor RAG: búsqueda semántica\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"QUERY CLÍNICO:\n{_QUERY}\n\n")
        f.write(f"ARTÍCULOS EN BASE DE CONOCIMIENTO: {collection.count()}\n\n")
        f.write("RESULTADOS POR RELEVANCIA SEMÁNTICA:\n")
        f.write("-" * 60 + "\n")
        for i, r in enumerate(resultados, 1):
            f.write(f"\n[{i}] Score de relevancia: {r.relevance_score:.3f}\n")
            f.write(f"    PMID   : {r.pmid}\n")
            f.write(f"    Título : {r.title}\n")
            f.write(f"    Revista: {r.journal} ({r.year})\n")
            f.write(f"    Autores: {r.authors}\n")
            f.write(f"    Excerpt: {r.excerpt[:200]}...\n")
        f.write(f"\nPMIDs para hipótesis TTR: {pmids}\n")

    # Artefacto 2: contexto listo para el agente
    contexto_txt = _OUT_DIR / "contexto_para_agente.txt"
    contexto_txt.write_text(
        "NEXUS — Contexto bibliográfico generado para prompt de agente\n"
        "=" * 60 + "\n\n"
        f"Query usado: \"{_QUERY}\"\n\n"
        + contexto,
        encoding="utf-8",
    )

    print()
    print(_SEP)
    print("  RESULTADO FINAL:")
    print(_SEP)
    print(f"  Artículos en base     : {collection.count()}")
    print(f"  Resultados top-3      : {len(resultados)} artículos con score ≥ 0.30")
    if resultados:
        print(f"  Mejor match           : PMID {resultados[0].pmid} (score {resultados[0].relevance_score:.3f})")
        print(f"    → {resultados[0].title}")
    print(f"  PMIDs para hipótesis  : {pmids}")
    print(f"  Contexto para agente  : {len(contexto)} caracteres")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • Query + resultados    → {query_txt}")
    print(f"    • Contexto para agente  → {contexto_txt}")
    print(_SEP)


if __name__ == "__main__":
    main()
