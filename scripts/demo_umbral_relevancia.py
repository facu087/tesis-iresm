"""
Demo — El umbral de relevancia del RAG (hallazgo A, tarjeta #76).

El `relevance_score` del retriever NO es la similitud coseno. ChromaDB devuelve
distancia coseno en [0, 2] y `rag/retriever.py` la convierte con
`1 - distancia/2`, o sea `score = (1 + coseno) / 2`. Con esa escala, el umbral
que estaba puesto —0,3— equivale a un coseno de **-0,4**: para texto biomédico
no descartaba nada. Ni siquiera un artículo ortogonal al query (coseno 0, score
0,5) quedaba afuera.

Este script mide dónde sí está el corte, sobre el corpus de
`scripts/demo_embeddings_comparacion.py`: 7 artículos de neuropatía más 1
deliberadamente fuera de dominio que funciona como control, y las tres queries
del caso de la tesis. Mide con los dos modelos que el sistema puede usar: el
biomédico por defecto y el general al que cae si falta `sentence-transformers`.

Necesita el modelo de embeddings en caché; no consulta PubMed ni usa cuota.

    python scripts/demo_umbral_relevancia.py

Artefactos en output/demo_umbral_relevancia/:
    medicion.txt   → la tabla por query y por modelo
    resumen.json   → las bandas medidas y el umbral elegido
"""

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.rag.retriever import _DEFAULT_MIN_RELEVANCE_SCORE, _ENV_MIN_SCORE_VAR

_RAIZ = Path(__file__).parent.parent
_OUT_DIR = _RAIZ / "output" / "demo_umbral_relevancia"
_SEP = "═" * 78
_SUB = "─" * 78

_MODELOS = [
    ("NeuML/pubmedbert-base-embeddings", "umb_pubmedbert", "biomédico (default)"),
    ("all-MiniLM-L6-v2", "umb_minilm", "general (fallback sin sentence-transformers)"),
]


def _cargar_corpus():
    """Importa el corpus y las queries del demo de comparación de embeddings."""
    spec = importlib.util.spec_from_file_location(
        "cmp_embeddings", _RAIZ / "scripts" / "demo_embeddings_comparacion.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def main() -> None:
    cmp = _cargar_corpus()
    lineas: list[str] = []
    resumen: dict = {"umbral_elegido": _DEFAULT_MIN_RELEVANCE_SCORE, "modelos": {}}

    def emitir(texto: str = "") -> None:
        print(texto)
        lineas.append(texto)

    emitir(_SEP)
    emitir("DEMO — Dónde cortar el filtro de relevancia del RAG")
    emitir(_SEP)
    emitir(f"\nEscala: score = 1 - distancia/2 = (1 + coseno) / 2")
    emitir(f"  score 1,00 = coseno  1,0 (idéntico)")
    emitir(f"  score 0,50 = coseno  0,0 (ortogonal, sin relación)")
    emitir(f"  score 0,30 = coseno -0,4  <- el umbral anterior")
    emitir(f"\nCorpus: {len(cmp._ARTICULOS)} artículos, control fuera de dominio "
           f"PMID {cmp._PMID_CONTROL}")

    for modelo, sufijo, etiqueta in _MODELOS:
        retriever, efectivo = cmp._indexar(modelo, sufijo)
        emitir(f"\n{_SUB}\nModelo: {efectivo}  —  {etiqueta}\n{_SUB}")

        peor_relevante, mejor_control = 1.0, 0.0
        por_query = {}
        for clave, query in cmp._QUERIES.items():
            # min_score=0.0 para ver el ranking completo, sin filtrar.
            resultados = retriever.search(query, max_results=50, min_score=0.0)
            scores = {r.pmid: r.relevance_score for r in resultados}
            control = scores.get(cmp._PMID_CONTROL, 0.0)
            relevantes = [s for p, s in scores.items() if p != cmp._PMID_CONTROL]

            mejor_control = max(mejor_control, control)
            peor_relevante = min(peor_relevante, min(relevantes))
            por_query[clave] = {"control": control,
                                "relevante_min": min(relevantes),
                                "relevante_max": max(relevantes)}
            emitir(f"  {clave:14} control={control:.3f}   "
                   f"relevantes {min(relevantes):.3f}–{max(relevantes):.3f}")

        separa = mejor_control < peor_relevante
        emitir(f"\n  banda libre: ({mejor_control:.3f} , {peor_relevante:.3f})"
               f"   {'separa' if separa else 'SE SOLAPAN'}")
        dentro = mejor_control < _DEFAULT_MIN_RELEVANCE_SCORE <= peor_relevante
        emitir(f"  umbral elegido {_DEFAULT_MIN_RELEVANCE_SCORE}: "
               f"{'cae en la banda' if dentro else 'NO cae en la banda'}")

        resumen["modelos"][efectivo] = {
            "etiqueta": etiqueta,
            "control_max": round(mejor_control, 3),
            "relevante_min": round(peor_relevante, 3),
            "separa": separa,
            "umbral_dentro_de_la_banda": dentro,
            "por_query": {k: {kk: round(vv, 3) for kk, vv in v.items()}
                          for k, v in por_query.items()},
        }

    bandas = resumen["modelos"].values()
    todas_separan = all(m["separa"] for m in bandas)
    todas_contienen = all(m["umbral_dentro_de_la_banda"] for m in bandas)

    emitir(f"\n{_SEP}")
    emitir(f"Umbral por defecto: {_DEFAULT_MIN_RELEVANCE_SCORE}  "
           f"(sobreescribible con {_ENV_MIN_SCORE_VAR})")
    emitir(f"{'[OK]' if todas_separan and todas_contienen else '[X]'} "
           + ("Con los dos modelos descarta el artículo fuera de dominio y no "
              "pierde ninguno relevante."
              if todas_separan and todas_contienen else
              "El umbral NO funciona para algún modelo: hay que volver a medir."))
    emitir("\nLimitación: la banda sale de UN artículo de control. Alcanza para "
           "dejar de\nusar un umbral inerte, no para afinarlo. Al cambiar de "
           "modelo, volver a medir.")
    emitir(_SEP)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "medicion.txt").write_text("\n".join(lineas), encoding="utf-8")
    (_OUT_DIR / "resumen.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nArtefactos: {_OUT_DIR}")

    sys.exit(0 if todas_separan and todas_contienen else 1)


if __name__ == "__main__":
    main()
