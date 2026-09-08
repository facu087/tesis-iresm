"""
Demo de verificación — Comparación de modelos de embeddings para el RAG.

Mide, sobre el caso de prueba del proyecto (neuropatía axonal, 42 años), qué
diferencia hace usar un modelo de embeddings biomédico frente al modelo general
que trae ChromaDB por defecto:

  A. NeuML/pubmedbert-base-embeddings  → PubMedBERT afinado para embeddings de
                                         oraciones (768 dims). Es el default del
                                         proyecto. Requiere sentence-transformers.
  B. all-MiniLM-L6-v2                  → default de ChromaDB, dominio general
                                         (384 dims). Sin dependencias extra.

Resultado de la comparación (corpus del caso de prueba, 8 artículos):
  - Ambos tienen dispersión de scores sana (0.218 vs 0.235 de amplitud).
  - PubMedBERT entiende mejor "hereditary": para la query de hipótesis TTR pone
    Charcot-Marie-Tooth segundo (la neuropatía hereditaria por antonomasia),
    mientras MiniLM pone déficit de B12, que no es hereditario.
  - PubMedBERT trae amiloidosis TTR al top-5 de la query del caso; MiniLM no.
  - Se descartó `pritamdeka/S-PubMedBert-MS-MARCO`: amplitud de scores 0.029
    (todo entre 0.951 y 0.980), lo que hace inservible el relevance_score.
  - Ninguno maneja la negación: con "negative CMT panel" los dos traen CMT.

Por qué NO se compara contra SciBERT: `allenai/scibert_scivocab_uncased` es un
modelo de lenguaje enmascarado, no un modelo de embeddings de oraciones.
Sacarle vectores por mean-pooling sin fine-tuning contrastivo rinde peor en
similitud semántica que un modelo entrenado para la tarea (Reimers & Gurevych,
2019). El dominio sería el correcto, la tarea no.

Qué mide
--------
1. Ranking top-5 de cada modelo para tres queries clínicas.
2. Coincidencia entre rankings (overlap@3 y @5): si ambos modelos traen los
   mismos artículos, cambiar de modelo no aporta nada en este corpus.
3. Dispersión de scores: un modelo que le da ~0.9 a todo no discrimina, aunque
   ordene bien.
4. Si el umbral `_MIN_RELEVANCE_SCORE` del retriever filtra algo. El score es
   `1 - distancia/2`, así que 0.3 equivale a coseno -0.4: se espera que no
   filtre nada, y el dato queda registrado.

Una de las queries está en español y su equivalente en inglés, a propósito: el
corpus indexado son abstracts de PubMed en inglés y ninguno de los dos modelos
es multilingüe. La comparación deja ver cuánto se pierde por consultar en
español (el mismo problema que motivó `condition_en` en la síntesis PICO).

Artefactos generados en output/demo_embeddings_comparacion/:
    1. rankings.txt   → top-5 de cada modelo, por query, lado a lado
    2. metricas.txt   → overlap, dispersión de scores y efecto del umbral
    3. resultados.json → todo lo anterior en JSON para procesar

Uso:
    python3 scripts/demo_embeddings_comparacion.py
    python3 scripts/demo_embeddings_comparacion.py <modelo_A> [modelo_B]

Los modelos se pueden pasar por argumento para evaluar alternativas sin tocar
código. Ej:
    python3 scripts/demo_embeddings_comparacion.py NeuML/pubmedbert-base-embeddings
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb

from backend.external.pubmed import PubMedArticle
from backend.rag.chroma_store import (
    BIOMEDICAL_EMBEDDING_MODEL,
    FALLBACK_EMBEDDING_MODEL,
    get_embedding_function,
)
from backend.rag.indexer import index_articles
from backend.rag.retriever import _MIN_RELEVANCE_SCORE, PubMedRetriever

_SEP = "═" * 78
_SUB = "─" * 78
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_embeddings_comparacion"

# ── Corpus ────────────────────────────────────────────────────────
# Artículos reales de PubMed relevantes (y algunos deliberadamente NO relevantes)
# para el caso de la tesis. Se usa un corpus fijo para que la comparación sea
# reproducible y no dependa de la red ni del estado de PubMed.
_ARTICULOS = [
    PubMedArticle(
        pmid="29470523",
        title="Hereditary transthyretin amyloidosis: a review",
        abstract=(
            "Hereditary transthyretin (ATTRv) amyloidosis is caused by mutations in the TTR gene. "
            "It manifests as progressive axonal polyneuropathy and cardiomyopathy. "
            "Patisiran and inotersen are approved RNA-targeted therapies that reduce TTR levels."
        ),
        journal="New England Journal of Medicine",
        year="2019",
        authors=["Adams D", "Gonzalez-Duarte A"],
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
        pmid="25439000",
        title="Vitamin B12 deficiency and peripheral neuropathy",
        abstract=(
            "Cobalamin deficiency causes subacute combined degeneration and axonal sensory neuropathy. "
            "Serum B12, methylmalonic acid and homocysteine establish the diagnosis. "
            "Parenteral replacement halts progression but deficits may persist."
        ),
        journal="Journal of the Neurological Sciences",
        year="2015",
        authors=["Green R", "Miller JW"],
    ),
    PubMedArticle(
        pmid="26597044",
        title="Paraneoplastic neurological syndromes: antibody testing and management",
        abstract=(
            "Onconeural antibodies including anti-Hu, anti-Yo and anti-Ri identify paraneoplastic "
            "syndromes. Sensory neuronopathy is the most frequent peripheral presentation. "
            "Tumour detection and treatment take precedence over immunotherapy."
        ),
        journal="Brain",
        year="2016",
        authors=["Graus F", "Dalmau J"],
    ),
    # Deliberadamente fuera de dominio: sirve como control. Si un modelo lo
    # ubica alto en el ranking, está discriminando mal.
    PubMedArticle(
        pmid="32109013",
        title="Machine learning for cardiac MRI segmentation: a systematic review",
        abstract=(
            "Deep convolutional networks achieve expert-level performance in cardiac chamber "
            "segmentation. U-Net architectures dominate the literature. "
            "External validation remains the main barrier to clinical adoption."
        ),
        journal="Medical Image Analysis",
        year="2020",
        authors=["Chen C", "Qin C"],
    ),
]

_PMID_CONTROL = "32109013"  # el artículo fuera de dominio

# ── Queries ───────────────────────────────────────────────────────
_QUERIES: dict[str, str] = {
    "caso_es": (
        "neuropatía axonal sensitivomotora progresiva en paciente masculino de "
        "42 años con diabetes tipo 2 y panel CMT negativo"
    ),
    "caso_en": (
        "progressive axonal sensorimotor neuropathy in a 42-year-old male with "
        "type 2 diabetes and a negative CMT panel"
    ),
    "hipotesis_en": (
        "hereditary transthyretin amyloidosis as a cause of progressive axonal "
        "neuropathy with family history"
    ),
}

_TOP_N = 5


def _indexar(modelo: str, sufijo: str) -> tuple[PubMedRetriever, str]:
    """
    Indexa el corpus en una colección propia para el modelo dado.

    Returns:
        (retriever, nombre_efectivo_del_modelo). El nombre efectivo difiere del
        pedido si hubo fallback por falta de sentence-transformers.
    """
    embedding_fn, efectivo = get_embedding_function(modelo)

    client = chromadb.EphemeralClient()
    collection = client.create_collection(
        name=f"cmp_{sufijo}",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine", "embedding_model": efectivo},
    )
    index_articles(_ARTICULOS, collection=collection)
    return PubMedRetriever(collection=collection), efectivo


def _rankear(retriever: PubMedRetriever) -> dict[str, list[dict]]:
    """Corre las tres queries y devuelve el top-N de cada una."""
    salida: dict[str, list[dict]] = {}
    for clave, query in _QUERIES.items():
        # min_score=0.0 para ver TODO el ranking, incluido lo que el umbral
        # del retriever dejaría pasar o filtraría.
        resultados = retriever.search(query, max_results=_TOP_N, min_score=0.0)
        salida[clave] = [
            {
                "pmid": r.pmid,
                "title": r.title,
                "score": r.relevance_score,
            }
            for r in resultados
        ]
    return salida


def _overlap(a: list[dict], b: list[dict], k: int) -> int:
    """Cantidad de PMIDs compartidos entre los top-k de dos rankings."""
    return len({x["pmid"] for x in a[:k]} & {x["pmid"] for x in b[:k]})


def _metricas(nombre: str, rankings: dict[str, list[dict]]) -> dict:
    """Dispersión de scores, posición del control y efecto del umbral."""
    todos = [x["score"] for r in rankings.values() for x in r]
    if not todos:
        return {"modelo": nombre, "sin_resultados": True}

    pos_control: dict[str, int | None] = {}
    for clave, r in rankings.items():
        pos = next((i + 1 for i, x in enumerate(r) if x["pmid"] == _PMID_CONTROL), None)
        pos_control[clave] = pos

    return {
        "modelo": nombre,
        "score_min": round(min(todos), 3),
        "score_max": round(max(todos), 3),
        "score_rango": round(max(todos) - min(todos), 3),
        "bajo_umbral": sum(1 for s in todos if s < _MIN_RELEVANCE_SCORE),
        "total_resultados": len(todos),
        "posicion_control": pos_control,
    }


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Comparación de modelos de embeddings para el RAG")
    print(_SEP)
    print(f"\n  Corpus: {len(_ARTICULOS)} artículos de PubMed (uno fuera de dominio como control)")
    print(f"  Queries: {len(_QUERIES)}  |  top-{_TOP_N} por query")

    modelo_a = sys.argv[1] if len(sys.argv) > 1 else BIOMEDICAL_EMBEDDING_MODEL
    modelo_b = sys.argv[2] if len(sys.argv) > 2 else FALLBACK_EMBEDDING_MODEL

    print(f"\n  [1/4] Indexando con el modelo biomédico...")
    ret_bio, modelo_bio = _indexar(modelo_a, "bio")
    print(f"        modelo efectivo: {modelo_bio}")

    print(f"\n  [2/4] Indexando con el modelo general...")
    ret_gen, modelo_gen = _indexar(modelo_b, "gen")
    print(f"        modelo efectivo: {modelo_gen}")

    comparable = modelo_bio != modelo_gen
    if not comparable:
        print(f"\n  ⚠ Los dos modelos efectivos son el mismo ({modelo_gen}).")
        print(f"    Falta `sentence-transformers`, así que el modelo biomédico cayó")
        print(f"    al fallback y NO hay nada que comparar.")
        print(f"    Para comparar de verdad:  pip install -r backend/requirements.txt")

    print(f"\n  [3/4] Corriendo queries en ambos modelos...")
    rank_bio = _rankear(ret_bio)
    rank_gen = _rankear(ret_gen)
    print(f"        ✓ {len(_QUERIES) * 2} búsquedas completadas")

    # ── Rankings lado a lado ──────────────────────────────────────
    lineas: list[str] = []
    for clave, query in _QUERIES.items():
        lineas.append(_SEP)
        lineas.append(f"QUERY [{clave}]")
        lineas.append(f"  {query}")
        lineas.append(_SUB)
        lineas.append(f"  {'BIOMÉDICO — ' + modelo_bio:<48} | GENERAL — {modelo_gen}")
        lineas.append(_SUB)

        for i in range(_TOP_N):
            b = rank_bio[clave][i] if i < len(rank_bio[clave]) else None
            g = rank_gen[clave][i] if i < len(rank_gen[clave]) else None
            izq = f"{i+1}. [{b['score']:.3f}] {b['pmid']} {b['title'][:26]}" if b else ""
            der = f"{i+1}. [{g['score']:.3f}] {g['pmid']} {g['title'][:26]}" if g else ""
            marca = "  " if (b and g and b["pmid"] == g["pmid"]) else "≠ "
            lineas.append(f"{marca}{izq:<48} | {der}")

        o3 = _overlap(rank_bio[clave], rank_gen[clave], 3)
        o5 = _overlap(rank_bio[clave], rank_gen[clave], _TOP_N)
        lineas.append(f"\n  Coincidencia: overlap@3 = {o3}/3   overlap@5 = {o5}/{_TOP_N}")
        lineas.append("")

    texto_rankings = "\n".join(lineas)
    print("\n" + texto_rankings)

    # ── Métricas ──────────────────────────────────────────────────
    m_bio = _metricas(modelo_bio, rank_bio)
    m_gen = _metricas(modelo_gen, rank_gen)

    met: list[str] = [_SEP, "MÉTRICAS", _SEP]
    for m in (m_bio, m_gen):
        met.append(f"\n  {m['modelo']}")
        met.append(f"    rango de scores: {m['score_min']} – {m['score_max']} "
                   f"(amplitud {m['score_rango']})")
        met.append(f"    resultados bajo el umbral {_MIN_RELEVANCE_SCORE}: "
                   f"{m['bajo_umbral']}/{m['total_resultados']}")
        met.append(f"    posición del artículo de control (fuera de dominio):")
        for clave, pos in m["posicion_control"].items():
            met.append(f"      {clave}: {'no entró al top-' + str(_TOP_N) if pos is None else 'puesto ' + str(pos)}")

    met.append(f"\n  Nota sobre el umbral: el score es 1 - distancia/2, así que")
    met.append(f"  {_MIN_RELEVANCE_SCORE} equivale a un coseno de "
               f"{2 * _MIN_RELEVANCE_SCORE - 1:.1f}. Si la columna 'bajo el umbral'")
    met.append(f"  da 0, el filtro de relevancia del retriever no descarta nada.")

    if comparable:
        prom_o5 = sum(_overlap(rank_bio[k], rank_gen[k], _TOP_N) for k in _QUERIES) / len(_QUERIES)
        met.append(f"\n  Overlap@5 promedio entre modelos: {prom_o5:.1f}/{_TOP_N}")
        met.append(f"  Cuanto más bajo, más cambia el modelo lo que ve el agente.")
    else:
        met.append(f"\n  ⚠ Comparación NO realizada: falta sentence-transformers.")

    texto_metricas = "\n".join(met)
    print("\n" + texto_metricas)

    # ── Artefactos ────────────────────────────────────────────────
    print(f"\n  [4/4] Guardando artefactos...")
    (_OUT_DIR / "rankings.txt").write_text(texto_rankings, encoding="utf-8")
    (_OUT_DIR / "metricas.txt").write_text(texto_metricas, encoding="utf-8")
    (_OUT_DIR / "resultados.json").write_text(
        json.dumps(
            {
                "comparable": comparable,
                "modelo_biomedico": modelo_bio,
                "modelo_general": modelo_gen,
                "umbral_retriever": _MIN_RELEVANCE_SCORE,
                "queries": _QUERIES,
                "rankings": {"biomedico": rank_bio, "general": rank_gen},
                "metricas": {"biomedico": m_bio, "general": m_gen},
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for f in sorted(_OUT_DIR.iterdir()):
        print(f"        ✓ {f.relative_to(_OUT_DIR.parent.parent)}")

    print(f"\n{_SEP}")
    print("  FIN" if comparable else "  FIN — comparación incompleta (ver aviso arriba)")
    print(_SEP)


if __name__ == "__main__":
    main()
