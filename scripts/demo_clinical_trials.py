"""
Demo de verificación — Cliente ClinicalTrials.gov API v2.

Busca ensayos clínicos ACTIVOS (reclutando) relacionados con el caso, conectando
las hipótesis de los agentes con oportunidades de investigación reales.

Este módulo NO usa el LLM: consulta directamente la API pública de
ClinicalTrials.gov (https://clinicaltrials.gov/api/v2/studies), sin autenticación
ni cupo. Es el mismo método (search_by_biomarkers) que usa el pipeline real.

Guarda como artefacto tangible para Trello:
    output/demo_clinical_trials/ensayos.json

Uso:
    python scripts/demo_clinical_trials.py
"""

import json
import sys
from pathlib import Path

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.external import clinical_trials

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_clinical_trials"

# Biomarcadores/condición derivados de las hipótesis de los agentes:
# la amiloidosis por TTR es una causa TRATABLE con ensayos activos.
_BIOMARKERS = ["TTR", "amyloidosis"]
_CONDITION = "amyloid neuropathy"


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Cliente ClinicalTrials.gov API v2")
    print(_SEP)
    print(f"  Condición de búsqueda : {_CONDITION}")
    print(f"  Biomarcadores         : {', '.join(_BIOMARKERS)}")
    print(f"  Filtro                : solo ensayos RECLUTANDO (activos)")
    print(_SEP)
    print("  Consultando la API pública de ClinicalTrials.gov…")
    print(_SEP)

    try:
        trials = clinical_trials.search_by_biomarkers(
            biomarkers=_BIOMARKERS,
            condition=_CONDITION,
            max_results=5,
        )
    except Exception as exc:
        print("  ⚠ No se pudo consultar la API:")
        print(f"    {type(exc).__name__}: {str(exc)[:160]}")
        print("    Verificá la conexión a internet y reintentá.")
        print(_SEP)
        return

    if not trials:
        print("  No se encontraron ensayos activos para esta búsqueda.")
        print(_SEP)
        return

    print(f"  ✓ {len(trials)} ensayos clínicos activos encontrados:")
    print(_SEP)

    for i, t in enumerate(trials, 1):
        print(f"  #{i} — {t.nct_id}  [{t.status}]")
        print(f"  Título: {t.title}")
        if t.phase:
            print(f"  Fase: {t.phase}")
        if t.conditions:
            print(f"  Condiciones: {', '.join(t.conditions[:4])}")
        if t.sponsor:
            print(f"  Patrocinador: {t.sponsor}")
        if t.locations:
            print(f"  Países: {', '.join(t.locations[:6])}")
        print(f"  Enlace: {t.url}")
        print()

    print(_SEP)

    # Guardar artefacto tangible
    salida = _OUT_DIR / "ensayos.json"
    salida.write_text(
        json.dumps([t.model_dump() for t in trials], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"  ✓ {len(trials)} ensayos recuperados de ClinicalTrials.gov.")
    print()
    print("  ARTEFACTO GENERADO (abrir y capturar para Trello):")
    print(f"    • Ensayos (JSON) → {salida}")
    print("  Tip: los enlaces son verificables — abrilos para mostrar que son reales.")
    print(_SEP)


if __name__ == "__main__":
    main()
