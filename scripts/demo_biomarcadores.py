"""
Demo de verificación — Extracción de biomarcadores y mapeo del historial terapéutico.

Identifica automáticamente genes, variantes, anticuerpos y biomarcadores de
laboratorio, y reconstruye el historial de tratamientos previos (fármacos,
procedimientos, cirugías).

El módulo combina DOS capas:
    • Capa 1 — Regex/diccionario: rápida y determinista (NO usa IA).
    • Capa 2 — LLM (Groq): captura entidades no previstas en el diccionario.
El resultado final fusiona ambas.

Este demo muestra la Capa 1 SIEMPRE (aunque Groq esté sin cupo) y el resultado
combinado si la API responde. Guarda el perfil resultante como artefacto:
    output/demo_biomarcadores/perfil_biomarcadores.json

Uso:
    python scripts/demo_biomarcadores.py
"""

import json
import sys
from pathlib import Path

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.ingestion.biomarker_extractor import (
    _extract_with_regex,
    extract,
)

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_biomarcadores"

# Texto clínico rico en entidades biomédicas e historial terapéutico.
_TEXTO = """\
Paciente con sospecha de neuropatía hereditaria.
Estudio genético: duplicación del gen PMP22. Genes MFN2 y TTR analizados.
Variante detectada: p.Val30Met en TTR.
Anticuerpos anti-MAG positivos.
Laboratorio: HbA1c 8.2 %, vitamina B12 disminuida, folato normal.
Electromiograma (EMG) con patrón axonal sensitivomotor.
Tratamiento previo: pregabalina y metilprednisolona.
Procedimientos realizados: biopsia de nervio sural."""


def _mostrar_lista(titulo: str, items: list[str]) -> None:
    if items:
        print(f"  {titulo}:")
        for it in items:
            print(f"     • {it}")
    else:
        print(f"  {titulo}: (ninguno)")


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Extracción de biomarcadores e historial terapéutico")
    print(_SEP)
    print("  TEXTO CLÍNICO DE ENTRADA:")
    print(_SEP)
    print(_TEXTO)
    print(_SEP)

    # ── Capa 1: regex/diccionario (siempre funciona, sin IA) ───────────────────
    regex = _extract_with_regex(_TEXTO)
    print("  CAPA 1 — Regex/diccionario (determinista, sin IA):")
    print(_SEP)
    _mostrar_lista("Genes", regex.get("genes_regex", []))
    _mostrar_lista("Variantes genéticas", regex.get("variants_regex", []))
    _mostrar_lista("Anticuerpos", regex.get("antibodies_regex", []))
    _mostrar_lista("Biomarcadores de lab", regex.get("lab_markers_regex", []))
    print(_SEP)

    # ── Capa 2 + fusión: requiere Groq ─────────────────────────────────────────
    print("  CAPA 2 — LLM (Groq) + fusión de ambas capas:")
    print(_SEP)
    try:
        perfil = extract(_TEXTO)
        print("  PERFIL COMBINADO (resultado final del módulo):")
        print()
        _mostrar_lista("Genes", perfil.genes)
        _mostrar_lista("Variantes genéticas", perfil.genetic_variants)
        _mostrar_lista("Anticuerpos", perfil.antibodies)
        _mostrar_lista("Biomarcadores de lab", perfil.lab_biomarkers)
        _mostrar_lista("Vías / síndromes", perfil.pathways)
        print()
        print("  HISTORIAL TERAPÉUTICO:")
        _mostrar_lista("Fármacos", perfil.drugs)
        _mostrar_lista("Procedimientos", perfil.procedures)
        _mostrar_lista("Cirugías", perfil.surgeries)

        salida = _OUT_DIR / "perfil_biomarcadores.json"
        salida.write_text(
            json.dumps(perfil.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(_SEP)
        print("  ✓ Extracción combinada exitosa.")
        print(f"    • Perfil completo → {salida}")
    except Exception as exc:
        print("  ⚠ La capa LLM no está disponible en este momento:")
        print(f"    {type(exc).__name__}: {str(exc)[:140]}")
        print()
        print("  La Capa 1 (regex) ya demostró la extracción determinista arriba.")
        print("  Reintentá cuando el límite diario de Groq se haya reseteado.")

        salida = _OUT_DIR / "perfil_biomarcadores_regex.json"
        salida.write_text(
            json.dumps(regex, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"    • Resultado de la Capa 1 → {salida}")
    print(_SEP)


if __name__ == "__main__":
    main()
