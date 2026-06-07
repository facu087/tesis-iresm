"""
Test de integración para extracción de biomarcadores e historial terapéutico.

Uso:
    python3 tests/test_biomarkers.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.ingestion.biomarker_extractor import extract

CASO_CLINICO = """
Paciente masculino de 42 años con neuropatía axonal sensitivomotora progresiva
de 18 meses de evolución. Compromiso autonómico asociado (hipotensión ortostática,
disfunción sudomotora). Panel genético reducido (CMT panel de 40 genes) negativo.
Electromiograma: axonal difuso sin desmielinización. LCR normal. Anticuerpos
paraneoplásicos estándar (anti-Hu, anti-Yo, anti-Ri) negativos. 3 años de
seguimiento sin diagnóstico. Edad de inicio: 40 años. Antecedentes familiares:
padre con "problemas de equilibrio" no estudiados.
""".strip()


def main():
    print("=" * 60)
    print("Test: Extracción de Biomarcadores e Historial Terapéutico")
    print("=" * 60)

    if not os.environ.get("GROQ_API_KEY"):
        print("⚠  GROQ_API_KEY no encontrada en .env")
        sys.exit(1)

    print("\nExtrayendo entidades clínicas...\n")
    profile = extract(CASO_CLINICO)

    print(f"Genes identificados:        {profile.genes or '—'}")
    print(f"Variantes genéticas:        {profile.genetic_variants or '—'}")
    print(f"Anticuerpos:                {profile.antibodies or '—'}")
    print(f"Biomarcadores de lab:       {profile.lab_biomarkers or '—'}")
    print(f"Vías/síndromes:             {profile.pathways or '—'}")
    print(f"Fármacos:                   {profile.drugs or '—'}")
    print(f"Procedimientos:             {profile.procedures or '—'}")
    print(f"Cirugías:                   {profile.surgeries or '—'}")
    print(f"\nResumen: {profile.summary()}")

    # ── Validación ─────────────────────────────────────────────────
    print("\n" + "─" * 60)
    errores = []
    # El caso tiene anticuerpos explícitos: anti-Hu, anti-Yo, anti-Ri
    if not profile.antibodies:
        errores.append("No se detectaron anticuerpos (se esperaban anti-Hu, anti-Yo, anti-Ri)")
    # El caso menciona EMG y LCR como procedimientos
    procs_lower = [p.lower() for p in profile.procedures]
    if not any("electro" in p or "emg" in p for p in procs_lower):
        errores.append("Electromiograma no detectado como procedimiento")
    # CMT es un gen/panel relevante
    genes_upper = [g.upper() for g in profile.genes]
    if "CMT" not in genes_upper:
        errores.append("Gen CMT no detectado")

    if errores:
        print("⚠  VALIDACIÓN CON OBSERVACIONES:")
        for e in errores:
            print(f"   • {e}")
    else:
        print("✅ Validación OK — Biomarcadores extraídos correctamente")

    # ── Exportar ───────────────────────────────────────────────────
    out = Path("output/biomarkers_result.json")
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(profile.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"\nJSON exportado: {out}")


if __name__ == "__main__":
    main()
