"""
Demo — Falsos positivos en el extractor de biomarcadores.

CMT, FAP y ATTR son siglas de ENFERMEDAD, no de gen, y el extractor las venía
reportando como "genes identificados". En el caso de la tesis el efecto es doble:
"CMT" aparece dentro de "CMT panel de 40 genes", que además es un hallazgo
NEGATIVO — el sistema informaba como gen encontrado justo lo que se descartó.

El arreglo obvio (sacarlas de _KNOWN_GENES) no cambia nada: _GENE_PATTERN
matchea cualquier sigla de 2-6 mayúsculas por su cuenta, y su único filtro es
_NON_GENE_TERMS. Este script muestra las tres situaciones.

No consulta APIs externas ni necesita GROQ_API_KEY: la capa LLM va mockeada.

    python scripts/demo_genes_falsos.py

Artefactos generados en output/demo_genes_falsos/:
    1. salida.txt   → la comparación completa
    2. resumen.json → perfil extraído antes y después
"""

import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.ingestion.biomarker_extractor import (
    _GENE_PATTERN,
    _KNOWN_GENES,
    _NON_GENE_TERMS,
    _extract_with_regex,
    extract,
)

_SEP = "═" * 78
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_genes_falsos"

CASO = (
    "Paciente masculino de 42 años con neuropatía axonal sensitivomotora "
    "progresiva de 18 meses. Panel genético reducido (CMT panel de 40 genes) "
    "NEGATIVO. Se descartan FAP y ATTR. Electromiograma axonal difuso. "
    "LCR normal. Se secuencia el gen TTR: variante p.Val30Met no detectada."
)


def _extraer_con(known_genes: set, non_gene_terms: set) -> list[str]:
    """Reproduce la capa regex con listas arbitrarias, para comparar escenarios."""
    encontrados = set()
    for m in _GENE_PATTERN.finditer(CASO):
        c = m.group()
        if c not in non_gene_terms and len(c) >= 2:
            encontrados.add(c)
    palabras = set(re.findall(r"\b[A-Z]{2,}\d*\b", CASO))
    encontrados.update(palabras & known_genes)
    return sorted(encontrados)


def main() -> None:
    print(_SEP)
    print("DEMO — Falsos positivos: siglas de enfermedad reportadas como genes")
    print(_SEP)
    print(f"\nENTRADA (caso de la tesis, recortado)\n  {CASO[:150]}…")

    enfermedades = {"CMT", "FAP", "ATTR"}

    print(f"\n{'─' * 78}\n1. ANTES — CMT/FAP/ATTR estaban en _KNOWN_GENES\n{'─' * 78}")
    antes = _extraer_con(_KNOWN_GENES | enfermedades, _NON_GENE_TERMS - enfermedades)
    print(f"  Genes identificados: {antes}")
    print("  → CMT, FAP y ATTR son enfermedades. CMT además viene de un")
    print("    hallazgo NEGATIVO ('CMT panel … NEGATIVO').")

    print(f"\n{'─' * 78}\n2. El arreglo que parecía obvio — solo sacarlas de _KNOWN_GENES\n{'─' * 78}")
    intermedio = _extraer_con(_KNOWN_GENES - enfermedades, _NON_GENE_TERMS - enfermedades)
    print(f"  Genes identificados: {intermedio}")
    print("  → Idéntico. _GENE_PATTERN matchea [A-Z]{2,6} por su cuenta y su")
    print("    único filtro es _NON_GENE_TERMS, no _KNOWN_GENES.")

    print(f"\n{'─' * 78}\n3. DESPUÉS — además en _NON_GENE_TERMS\n{'─' * 78}")
    despues = _extract_with_regex(CASO)["genes_regex"]
    print(f"  Genes identificados: {despues}")
    print("  → Queda TTR, que es el gen real de la amiloidosis ATTR y sí está")
    print("    mencionado como gen en el texto.")

    print(f"\n{'─' * 78}\n4. La otra mitad — el LLM también devuelve enfermedades\n{'─' * 78}")
    respuesta_llm = {
        "genes": ["CMT", "ATTR", "PMP22"],
        "antibodies": [], "lab_biomarkers": [], "genetic_variants": [],
        "pathways": ["neuropatía axonal"],
        "therapeutic_history": {"drugs": [], "procedures": [], "surgeries": []},
    }
    with patch(
        "backend.ingestion.biomarker_extractor._extract_with_llm",
        return_value=respuesta_llm,
    ):
        perfil = extract(CASO)
    print(f"  El LLM devolvió     : {respuesta_llm['genes']}")
    print(f"  Perfil final        : {perfil.genes}")
    print("  → _merge_results() filtra también el lado del LLM: limpiar solo el")
    print("    diccionario dejaba el síntoma intacto.")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    resumen = _OUT_DIR / "resumen.json"
    resumen.write_text(
        json.dumps(
            {
                "caso": CASO,
                "antes": antes,
                "solo_sacando_de_known_genes": intermedio,
                "despues_regex": despues,
                "genes_del_llm": respuesta_llm["genes"],
                "perfil_final": perfil.genes,
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n{_SEP}\nArtefacto: {resumen}\n{_SEP}")


if __name__ == "__main__":
    main()
