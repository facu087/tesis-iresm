"""
Test de integración para la síntesis PICO.
Usa el caso de prueba neurológico del Sprint 1.

Uso:
    python3 tests/test_pico.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.models.case import ClinicalCase
from backend.pipeline import pico

CASO_CLINICO = """
Paciente masculino de 42 años con neuropatía axonal sensitivomotora progresiva
de 18 meses de evolución. Compromiso autonómico asociado (hipotensión ortostática,
disfunción sudomotora). Panel genético reducido (CMT panel de 40 genes) negativo.
Electromiograma: axonal difuso sin desmielinización. LCR normal. Anticuerpos
paraneoplásicos estándar (anti-Hu, anti-Yo, anti-Ri) negativos. 3 años de
seguimiento sin diagnóstico. Edad de inicio: 40 años. Antecedentes familiares:
padre con "problemas de equilibrio" no estudiados.
""".strip()


# ── Tests del parser (deterministas, sin llamadas a la API) ───────────────────

def _pico_json(**extra) -> str:
    """JSON PICO mínimo válido, para probar el parseo."""
    data = {
        "patient_profile": "Masculino de 42 años",
        "chief_complaint": "Neuropatía axonal sensitivomotora progresiva",
        "relevant_history": [],
        "negative_findings": [],
        "disease_duration": "18 meses",
        "current_treatments": [],
        "procedures_done": [],
        "comparison": "No aplica",
        "primary_outcome": "Identificar la etiología",
        "secondary_outcomes": [],
        "biomarkers": [],
        "genetic_findings": [],
        "clinical_narrative": "Narrativa del caso.",
    }
    data.update(extra)
    return json.dumps(data, ensure_ascii=False)


def test_parse_pico_toma_condition_en():
    """condition_en se parsea y queda disponible para las APIs externas."""
    p = pico._parse_pico(_pico_json(condition_en="axonal neuropathy"))
    assert p.condition_en == "axonal neuropathy"


def test_parse_pico_sin_condition_en_usa_default():
    """Un PICO sin condition_en sigue siendo válido (reportes previos al campo)."""
    p = pico._parse_pico(_pico_json())
    assert p.condition_en == ""
    assert p.chief_complaint  # el resto del parseo no se ve afectado


def test_condition_en_no_pisa_al_chief_complaint():
    """El campo en inglés es adicional: la narrativa clínica sigue en español."""
    p = pico._parse_pico(_pico_json(condition_en="axonal neuropathy"))
    assert p.chief_complaint == "Neuropatía axonal sensitivomotora progresiva"


def main():
    print("=" * 60)
    print("Test: Síntesis PICO")
    print("Caso: Neuropatía axonal sensitivomotora, 42 años")
    print("=" * 60)

    if not os.environ.get("GROQ_API_KEY"):
        print("⚠  GROQ_API_KEY no encontrada en .env")
        sys.exit(1)

    case = ClinicalCase(raw_text=CASO_CLINICO)
    print("\nConstruyendo síntesis PICO...\n")

    case = pico.build(case)
    p = case.pico

    # ── Mostrar resultado ──────────────────────────────────────────
    print(f"PERFIL:     {p.patient_profile}")
    print(f"CONSULTA:   {p.chief_complaint}")
    print(f"DURACIÓN:   {p.disease_duration}")
    print(f"\nANTECEDENTES ({len(p.relevant_history)}):")
    for h in p.relevant_history:
        print(f"  - {h}")
    print(f"\nESTUDIOS NEGATIVOS ({len(p.negative_findings)}):")
    for f in p.negative_findings:
        print(f"  - {f}")
    print(f"\nBIOMARCADORES: {p.biomarkers or 'ninguno identificado'}")
    print(f"HALLAZGOS GENÉTICOS: {p.genetic_findings or 'ninguno'}")
    print(f"\nOBJETIVO PRINCIPAL: {p.primary_outcome}")
    print(f"\nNARRATIVA CLÍNICA:\n{p.clinical_narrative}")

    # ── Formato para agentes ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("CONTEXTO FORMATEADO PARA AGENTES:")
    print("=" * 60)
    print(pico.format_for_agents(p))

    # ── Validación mínima ──────────────────────────────────────────
    print("\n" + "─" * 60)
    errores = []
    if not p.patient_profile:
        errores.append("patient_profile vacío")
    if not p.negative_findings:
        errores.append("negative_findings vacío (crítico para este caso)")
    if not p.clinical_narrative or len(p.clinical_narrative) < 100:
        errores.append("clinical_narrative muy corto")
    if len(p.procedures_done) < 2:
        errores.append("procedures_done incompleto (se esperan al menos EMG y LCR)")

    if errores:
        print("⚠  VALIDACIÓN CON OBSERVACIONES:")
        for e in errores:
            print(f"   • {e}")
    else:
        print("✅ Validación OK — Síntesis PICO completa y coherente")

    # ── Exportar JSON ──────────────────────────────────────────────
    out = Path("output/pico_result.json")
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(case.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"\nJSON exportado: {out}")


if __name__ == "__main__":
    main()
