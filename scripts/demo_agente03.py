"""
Demo de verificación — Agente 03: Consultor Clínico.

A partir del mismo contexto clínico, este agente genera hipótesis desde el
RAZONAMIENTO CLÍNICO (no desde la literatura como el Agente 01): patrones de
presentación, criterios diagnósticos, causas TRATABLES a descartar primero y
guías de sociedades médicas (AAN, EFNS, NCCN).

La diferencia de enfoque entre el Agente 01 y el 03 es el núcleo del diseño
multi-agente: dos perspectivas distintas sobre el mismo caso.

NOTA: la arquitectura final asigna este agente a Gemini Pro; hoy corre con Groq
(LLaMA 3.3). Una sola llamada al LLM.

Guarda como artefacto tangible para Trello:
    output/demo_agente03/hipotesis_agente03.json

Uso:
    python scripts/demo_agente03.py
"""

import json
import sys
from pathlib import Path

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.agents.agent_03_clinical import ClinicalConsultantAgent

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_agente03"

# Mismo contexto clínico que el demo del Agente 01 (para comparar enfoques).
_CONTEXTO = """\
=== SÍNTESIS CLÍNICA ESTRUCTURADA (PICO) ===

PERFIL DEL PACIENTE: Paciente masculino de 42 años.
MOTIVO DE CONSULTA: Neuropatía axonal sensitivomotora progresiva.
DURACIÓN: 18 meses.
COMPROMISO AUTONÓMICO: hipotensión ortostática, disfunción sudomotora.
ESTUDIOS NEGATIVOS (crítico para diagnóstico diferencial):
  - Panel genético CMT (40 genes) negativo
  - LCR normal
  - Anticuerpos paraneoplásicos (anti-Hu, anti-Yo, anti-Ri) negativos
PROCEDIMIENTOS: electromiografía (patrón axonal difuso, sural ausente bilateral).
ANTECEDENTES: diabetes tipo 2 (10 años, HbA1c 8.2%); padre con problemas de equilibrio.
TRATAMIENTO: pregabalina 150 mg/día.
OBJETIVO: determinar la etiología de la neuropatía tras 3 años sin diagnóstico."""

_PRIORIDAD = {"HIGH": "ALTA", "MEDIUM": "MEDIA", "LOW": "BAJA"}


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Agente 03: Consultor Clínico")
    print(_SEP)
    print("  CONTEXTO CLÍNICO DE ENTRADA (salida de la síntesis PICO):")
    print(_SEP)
    print(_CONTEXTO)
    print(_SEP)
    print("  Ejecutando agente (1 llamada al LLM vía Groq)…")
    print(_SEP)

    agent = ClinicalConsultantAgent()
    try:
        output = agent.run(_CONTEXTO)
    except Exception as exc:
        print("  ⚠ El agente no pudo completar (probablemente límite de Groq):")
        print(f"    {type(exc).__name__}: {str(exc)[:140]}")
        print("    Reintentá cuando el cupo de la API se haya reseteado.")
        print(_SEP)
        return

    print(f"  AGENTE: {output.agent_name} (ID {output.agent_id})")
    print(f"  HIPÓTESIS GENERADAS: {len(output.hypotheses)}")
    print(_SEP)

    for i, h in enumerate(output.hypotheses, 1):
        prio = _PRIORIDAD.get(h.priority.value, h.priority.value)
        print(f"  #{i} — [Prioridad {prio} · Evidencia nivel {h.evidence_level.value}]")
        print(f"  Hipótesis: {h.text}")
        print(f"  Razonamiento clínico: {h.rationale}")
        if h.sources:
            print("  Guías / fuentes:")
            for s in h.sources:
                ref = s.title
                if s.journal:
                    ref += f" — {s.journal}"
                if s.year:
                    ref += f" ({s.year})"
                if s.pmid:
                    ref += f" [PMID: {s.pmid}]"
                print(f"     • {ref}")
        else:
            print("  Guías / fuentes: (razonamiento fisiopatológico, sin referencia)")
        print()

    print(_SEP)

    # Guardar artefacto tangible (sin la respuesta cruda del LLM)
    salida = _OUT_DIR / "hipotesis_agente03.json"
    salida.write_text(
        json.dumps(output.model_dump(exclude={"raw_response"}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"  ✓ {len(output.hypotheses)} hipótesis generadas y validadas (Pydantic).")
    print()
    print("  ARTEFACTO GENERADO (abrir y capturar para Trello):")
    print(f"    • Hipótesis (JSON) → {salida}")
    print(_SEP)


if __name__ == "__main__":
    main()
