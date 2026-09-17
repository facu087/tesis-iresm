"""
Demo de verificación — Orquestador: distribución paralela (Ronda 1).

El orquestador corre los Agentes 01 (Literatura), 02 (Genómica) y 03 (Clínico) EN PARALELO
sobre el mismo contexto clínico (asyncio.gather + to_thread), y consolida sus
hipótesis en un único Report con resumen de fuentes por nivel de evidencia.

Características que demuestra:
    • Ejecución concurrente de los agentes (no secuencial).
    • Consolidación de hipótesis de múltiples agentes.
    • Resiliencia: si un agente falla, el pipeline continúa con el resto.

Para enfocar el demo en el orquestador, la síntesis PICO se arma a mano (sin
llamar al LLM): así las únicas 2 llamadas a Groq son las de los dos agentes.

Guarda como artefacto tangible para Trello:
    output/demo_orquestador/reporte_ronda1.json

Uso:
    python scripts/demo_orquestador.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.models.case import ClinicalCase, PICOSynthesis
from backend.pipeline import orchestrator

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_orquestador"

# Síntesis PICO precargada (caso base de la tesis) — evita una llamada a Groq.
_PICO = PICOSynthesis(
    patient_profile="Paciente masculino de 42 años",
    chief_complaint="Neuropatía axonal sensitivomotora progresiva",
    relevant_history=["Diabetes tipo 2 de 10 años (HbA1c 8.2%)",
                      "Padre con problemas de equilibrio no estudiados"],
    negative_findings=["Panel genético CMT (40 genes) negativo",
                       "LCR normal",
                       "Anticuerpos paraneoplásicos (anti-Hu, anti-Yo, anti-Ri) negativos"],
    disease_duration="18 meses",
    current_treatments=["Pregabalina 150 mg/día"],
    procedures_done=["Electromiografía (patrón axonal difuso, sural ausente bilateral)"],
    comparison="No aplica",
    primary_outcome="Determinar la etiología de la neuropatía tras 3 años sin diagnóstico",
    secondary_outcomes=["Identificar causas tratables", "Evaluar compromiso autonómico"],
    biomarkers=["HbA1c 8.2%"],
    genetic_findings=["Panel CMT negativo"],
    clinical_narrative=(
        "Paciente masculino de 42 años con neuropatía axonal sensitivomotora "
        "progresiva de 18 meses, con compromiso autonómico (hipotensión ortostática, "
        "disfunción sudomotora). EMG axonal difuso. Panel CMT, LCR y anticuerpos "
        "paraneoplásicos negativos. Diabetes tipo 2. Tres años sin diagnóstico etiológico."
    ),
)

_PRIORIDAD = {"HIGH": "ALTA", "MEDIUM": "MEDIA", "LOW": "BAJA"}


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    case = ClinicalCase(raw_text="(precargado)", pico=_PICO)

    print(_SEP)
    print("  DEMO — Orquestador: distribución paralela (Ronda 1)")
    print(_SEP)
    print("  CONTEXTO: síntesis PICO del caso (neuropatía axonal, 42 años).")
    print("  AGENTES A EJECUTAR EN PARALELO:")
    print("     • Agente 01 — Analista de Literatura")
    print("     • Agente 03 — Consultor Clínico")
    print(_SEP)
    print("  Ejecutando Ronda 1 (asyncio.gather — 3 llamadas concurrentes a Groq)…")
    print(_SEP)

    try:
        t0 = time.perf_counter()
        report = asyncio.run(orchestrator.run_round_1(case))
        elapsed = time.perf_counter() - t0
    except Exception as exc:
        print("  ⚠ La Ronda 1 no pudo completar (probablemente límite de Groq):")
        print(f"    {type(exc).__name__}: {str(exc)[:140]}")
        print("    Reintentá cuando el cupo de la API se haya reseteado.")
        print(_SEP)
        return

    print(f"  ✓ Ronda 1 completada en {elapsed:.1f} s (ambos agentes en paralelo).")
    print(f"  Agentes que respondieron: {len(report.agent_outputs)} de 3")
    print(f"  Total de hipótesis consolidadas: {len(report.hypotheses)}")
    print(_SEP)

    # Desglose por agente
    print("  HIPÓTESIS POR AGENTE:")
    for out in report.agent_outputs:
        print(f"\n  ── {out.agent_name} (ID {out.agent_id}) — {len(out.hypotheses)} hipótesis ──")
        for i, h in enumerate(out.hypotheses, 1):
            prio = _PRIORIDAD.get(h.priority.value, h.priority.value)
            print(f"     #{i} [{prio} · Ev. {h.evidence_level.value}] {h.text}")
    print(_SEP)

    # Resumen de fuentes por nivel de evidencia
    print("  RESUMEN DE FUENTES (por nivel de evidencia):")
    for nivel in ("I", "II", "III"):
        print(f"     Nivel {nivel}: {report.sources_summary.get(nivel, 0)} fuentes")
    print(_SEP)

    # Guardar artefacto (Report sin las respuestas crudas de cada agente)
    salida = _OUT_DIR / "reporte_ronda1.json"
    salida.write_text(
        json.dumps(
            report.model_dump(exclude={"agent_outputs": {"__all__": {"raw_response"}}}),
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    print(f"  ✓ Reporte consolidado de Ronda 1 generado.")
    print()
    print("  ARTEFACTO GENERADO (abrir y capturar para Trello):")
    print(f"    • Reporte Ronda 1 (JSON) → {salida}")
    print(_SEP)


if __name__ == "__main__":
    main()
