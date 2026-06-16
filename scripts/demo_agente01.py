"""
Demo de verificación — Agente 01: Analista de Literatura.

A partir del contexto clínico estructurado, el agente genera hipótesis de
investigación priorizadas, con nivel de evidencia y referencias bibliográficas.
Es el primer agente del pipeline y el corazón del sistema (genera las hipótesis).

De paso ejercita la clase base BaseAgent: la llamada al LLM y el parseo/validación
del JSON de hipótesis son lógica heredada que todos los agentes comparten.

NOTA: la arquitectura final asigna este agente a Claude; hoy corre con Groq
(LLaMA 3.3), el modelo que reemplaza temporalmente a Claude. Una sola llamada al LLM.

Guarda como artefacto tangible para Trello:
    output/demo_agente01/hipotesis_agente01.json

Uso:
    python scripts/demo_agente01.py
"""

import json
import sys
from pathlib import Path

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.agents.agent_01_literature import LiteratureAnalystAgent

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_agente01"

# Contexto clínico estructurado (como el que produce la síntesis PICO).
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
    print("  DEMO — Agente 01: Analista de Literatura")
    print(_SEP)
    print("  CONTEXTO CLÍNICO DE ENTRADA (salida de la síntesis PICO):")
    print(_SEP)
    print(_CONTEXTO)
    print(_SEP)
    print("  Ejecutando agente (1 llamada al LLM vía Groq)…")
    print(_SEP)

    agent = LiteratureAnalystAgent()
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
        print(f"  Fundamento: {h.rationale}")
        if h.sources:
            print("  Fuentes:")
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
            print("  Fuentes: (hipótesis especulativa, sin referencia verificable)")
        print()

    print(_SEP)

    # Guardar artefacto tangible (sin la respuesta cruda del LLM)
    salida = _OUT_DIR / "hipotesis_agente01.json"
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
