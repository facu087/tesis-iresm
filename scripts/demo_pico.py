"""
Demo de verificación — Síntesis PICO (construcción de narrativa clínica estructurada).

Transforma texto clínico crudo en una estructura PICO (Población, Intervención,
Comparación, Outcome) usando un prompt especializado + LLM. Esta síntesis es el
contexto estructurado que reciben TODOS los agentes de análisis en la Ronda 1.

NOTA: la tarjeta menciona "Claude API", pero el módulo corre hoy con Groq
(LLaMA 3.3), el modelo que reemplaza temporalmente a Claude mientras se gestionan
los créditos. La arquitectura no cambia: solo el cliente del LLM.

Muestra tres niveles y guarda artefactos tangibles para Trello:
    1. La estructura PICO completa → output/demo_pico/pico_synthesis.json
    2. El contexto para los agentes → output/demo_pico/contexto_agentes.txt

Uso:
    python scripts/demo_pico.py
"""

import json
import sys
from pathlib import Path

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.models.case import ClinicalCase
from backend.pipeline import pico

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_pico"

# Caso clínico base de la tesis (neuropatía axonal, 42 años, anonimizado).
_TEXTO = """\
Paciente masculino de 42 años con neuropatía axonal sensitivomotora progresiva
de 18 meses de evolución. Debilidad progresiva en miembros inferiores y compromiso
autonómico asociado (hipotensión ortostática, disfunción sudomotora).
Electromiografía: patrón axonal difuso, velocidad de conducción disminuida,
potenciales sensoriales ausentes en nervio sural bilateral.
Panel genético CMT (40 genes) negativo. LCR normal.
Anticuerpos paraneoplásicos (anti-Hu, anti-Yo, anti-Ri) negativos.
Antecedentes: diabetes tipo 2 de 10 años, HbA1c 8.2%. Padre con problemas de
equilibrio no estudiados. Tratamiento actual: pregabalina 150 mg/día.
Tres años de seguimiento sin diagnóstico etiológico."""


def _bloque(titulo: str, valor) -> None:
    if isinstance(valor, list):
        if valor:
            print(f"  {titulo}:")
            for v in valor:
                print(f"     • {v}")
        else:
            print(f"  {titulo}: (ninguno)")
    else:
        print(f"  {titulo}: {valor}")


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Síntesis PICO (texto clínico → estructura PICO)")
    print(_SEP)
    print("  TEXTO CLÍNICO CRUDO DE ENTRADA:")
    print(_SEP)
    print(_TEXTO)
    print(_SEP)

    try:
        case = pico.build(ClinicalCase(raw_text=_TEXTO))
    except Exception as exc:
        print("  ⚠ El módulo PICO no pudo completar (probablemente límite de Groq):")
        print(f"    {type(exc).__name__}: {str(exc)[:140]}")
        print("    Reintentá cuando el cupo de la API se haya reseteado.")
        print(_SEP)
        return

    p = case.pico

    print("  ESTRUCTURA PICO GENERADA:")
    print(_SEP)
    print("  ── P — POBLACIÓN ──")
    _bloque("Perfil del paciente", p.patient_profile)
    _bloque("Motivo de consulta", p.chief_complaint)
    _bloque("Duración", p.disease_duration)
    _bloque("Antecedentes relevantes", p.relevant_history)
    _bloque("Estudios negativos", p.negative_findings)
    print()
    print("  ── I — INTERVENCIÓN ──")
    _bloque("Tratamientos", p.current_treatments)
    _bloque("Procedimientos", p.procedures_done)
    print()
    print("  ── C — COMPARACIÓN ──")
    _bloque("Comparación", p.comparison)
    print()
    print("  ── O — OUTCOME ──")
    _bloque("Objetivo principal", p.primary_outcome)
    _bloque("Objetivos secundarios", p.secondary_outcomes)
    print()
    print("  ── EXTRAS ──")
    _bloque("Biomarcadores", p.biomarkers)
    _bloque("Hallazgos genéticos", p.genetic_findings)
    print(_SEP)
    print("  NARRATIVA CLÍNICA INTEGRADA (lo que sintetiza el modelo):")
    print(_SEP)
    print(f"  {p.clinical_narrative}")
    print(_SEP)

    # Guardar artefactos tangibles
    json_out = _OUT_DIR / "pico_synthesis.json"
    json_out.write_text(
        json.dumps(p.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ctx_out = _OUT_DIR / "contexto_agentes.txt"
    ctx_out.write_text(pico.format_for_agents(p), encoding="utf-8")

    print("  ✓ Síntesis PICO construida correctamente.")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • Estructura PICO (JSON)     → {json_out}")
    print(f"    • Contexto para los agentes  → {ctx_out}")
    print(_SEP)


if __name__ == "__main__":
    main()
