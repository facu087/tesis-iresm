"""
Demo de verificación — Telemetría de costos (control de costos, Sprint 4).

Muestra entrada → salida de dos piezas del control de costos:

  1. **Mecanismo real, sin gastar cuota.** Corre `pico.build()` y
     `biomarker_extractor.extract()` con el modo mock activo
     (`NEXUS_MOCK_LLM=1`) dentro de un registro de telemetría abierto, para
     mostrar que `call_provider()` + `telemetry.usage` funcionan juntos de
     punta a punta sin tocar la red. Los tokens de esta parte dan 0: el modo
     mock no consume nada de verdad (no es la corrida que mide costo real).

  2. **Comparación de costo, con una muestra sintética.** Esta sesión de
     implementación tiene prohibido llamar a Groq (es la restricción que este
     mismo cambio existe para poder medir y respetar), así que no hay una
     corrida real de la que sacar conteos de tokens todavía. En su lugar arma
     un registro con conteos **plausibles pero inventados** —anotados como
     tales—, del orden de magnitud que documenta `.claude/CLAUDE.md`
     (17 a 20 llamadas por caso), y muestra:
       - el desglose de tokens por agente,
       - el costo con las tarifas de Groq (cero),
       - el costo que tendría el mismo consumo con los modelos de la
         arquitectura de destino (Claude Opus, GPT-4o, Gemini Pro), usando
         `usage.recalculate()` — la razón de ser de la tabla de tarifas
         (D5): poder responder esa pregunta sin correr nada.

Uso:
    python3 scripts/demo_costos.py

Artefactos en output/demo_costos/:
    mecanismo_mock.json       → resumen de telemetría del análisis en modo mock
    muestra_sintetica.json    → resumen de telemetría de la muestra inventada
    comparacion_costos.txt    → desglose legible: Groq vs. arquitectura de destino
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json

from dotenv import load_dotenv

load_dotenv()

import os

# Se fuerza ANTES de importar nada de backend.agents/backend.pipeline: el modo
# mock se lee de la variable de entorno en el momento de la llamada, pero
# fijarlo acá dejar explícito que este demo nunca toca la red ni gasta cuota.
os.environ["NEXUS_MOCK_LLM"] = "1"

from backend.ingestion import biomarker_extractor
from backend.models.case import ClinicalCase
from backend.pipeline import pico
from backend.telemetry import pricing, usage

_SEP = "═" * 78
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_costos"

_CASO_CLINICO = (
    "Paciente masculino de 42 años con neuropatía axonal sensitivomotora "
    "progresiva de 18 meses de evolución, en tratamiento con metformina."
)

# Tarifas de la arquitectura de destino (.claude/CLAUDE.md — "Modelo de IA").
# Valores de lista pública al momento de escribir esto: hay que revisarlos
# antes de usarlos para el capítulo de viabilidad de la tesis (por eso viven
# acá, en un demo, y no activados en pricing.DEFAULT_PRICES).
_TARIFAS_DESTINO = {
    # Sustituyen a GROQ_MAIN/GROQ_FAST en la comparación: mismo conteo de
    # tokens, otro proveedor.
    "openai/gpt-oss-120b": pricing.ModelPrice(input_per_million=15.0, output_per_million=75.0),   # ~Claude Opus
    "openai/gpt-oss-20b": pricing.ModelPrice(input_per_million=2.5, output_per_million=10.0),      # ~GPT-4o
}

# Muestra sintética: 18 llamadas (Ronda 1 x3, críticas x3, revisiones x6,
# Árbitro x2, Agente 05 x2, PICO x1, biomarcadores x1), con conteos de tokens
# plausibles para cada tarea según su naturaleza (razonamiento vs. salida
# acotada). NO son una corrida real: ver el docstring del módulo.
_MUESTRA_SINTETICA: list[dict] = [
    {"task": "agente01_hipotesis", "agent_id": "01", "agent_name": "Analista de Literatura",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 2400, "completion_tokens": 1100},
    {"task": "agente02_hipotesis", "agent_id": "02", "agent_name": "Especialista Genómica",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 2600, "completion_tokens": 1000},
    {"task": "agente03_hipotesis", "agent_id": "03", "agent_name": "Consultor Clínico",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 2300, "completion_tokens": 1150},
    {"task": "debate_critica", "agent_id": "01", "agent_name": "Analista de Literatura",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 3200, "completion_tokens": 600},
    {"task": "debate_critica", "agent_id": "02", "agent_name": "Especialista Genómica",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 3200, "completion_tokens": 650},
    {"task": "debate_critica", "agent_id": "03", "agent_name": "Consultor Clínico",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 3200, "completion_tokens": 580},
    {"task": "debate_revision", "agent_id": "01", "agent_name": "Analista de Literatura",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 3600, "completion_tokens": 1200},
    {"task": "debate_revision", "agent_id": "02", "agent_name": "Especialista Genómica",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 3600, "completion_tokens": 1100},
    {"task": "debate_revision", "agent_id": "03", "agent_name": "Consultor Clínico",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 3600, "completion_tokens": 1150},
    {"task": "debate_revision", "agent_id": "01", "agent_name": "Analista de Literatura",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 3800, "completion_tokens": 1150},
    {"task": "debate_revision", "agent_id": "02", "agent_name": "Especialista Genómica",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 3800, "completion_tokens": 1050},
    {"task": "debate_revision", "agent_id": "03", "agent_name": "Consultor Clínico",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 3800, "completion_tokens": 1100},
    {"task": "arbitro_agrupacion", "agent_id": "04", "agent_name": "Árbitro Verificador",
     "model": "openai/gpt-oss-20b", "prompt_tokens": 900, "completion_tokens": 90},
    {"task": "arbitro_veredictos", "agent_id": "04", "agent_name": "Árbitro Verificador",
     "model": "openai/gpt-oss-120b", "prompt_tokens": 1800, "completion_tokens": 700},
    {"task": "agente05_planificacion_terminos", "agent_id": "05", "agent_name": "Navegador de Ensayos",
     "model": "openai/gpt-oss-20b", "prompt_tokens": 500, "completion_tokens": 180},
    {"task": "agente05_evaluacion_compatibilidad", "agent_id": "05", "agent_name": "Navegador de Ensayos",
     "model": "openai/gpt-oss-20b", "prompt_tokens": 2200, "completion_tokens": 900},
    {"task": "pico_sintesis", "agent_id": None, "agent_name": None,
     "model": "openai/gpt-oss-120b", "prompt_tokens": 900, "completion_tokens": 650},
    {"task": "biomarcadores_extraccion", "agent_id": None, "agent_name": None,
     "model": "openai/gpt-oss-120b", "prompt_tokens": 700, "completion_tokens": 300},
]


def _correr_mecanismo_real_en_modo_mock() -> dict:
    """Ejercita call_provider() + telemetry.usage con el modo mock, sin red."""
    token = usage.open_registry()
    pico.build(ClinicalCase(raw_text=_CASO_CLINICO))
    biomarker_extractor.extract(_CASO_CLINICO)
    return usage.close_registry(token, output_path=_OUT_DIR / "_no_usar.jsonl", mock=True)


def _armar_muestra_sintetica() -> dict:
    """Arma un resumen de telemetría a partir de `_MUESTRA_SINTETICA`, sin llamar a nada."""
    token = usage.open_registry()
    for llamada in _MUESTRA_SINTETICA:
        usage.record_call(
            task=llamada["task"], model=llamada["model"],
            agent_id=llamada["agent_id"], agent_name=llamada["agent_name"],
            ok=True, latency_seconds=1.5,
            prompt_tokens=llamada["prompt_tokens"], completion_tokens=llamada["completion_tokens"],
        )
    return usage.close_registry(token, output_path=_OUT_DIR / "_no_usar.jsonl")


def _tabla_comparativa(resumen: dict) -> str:
    """Arma el texto legible: costo con Groq vs. con la arquitectura de destino."""
    con_destino = usage.recalculate(resumen, _TARIFAS_DESTINO)
    t = resumen["totals"]
    td = con_destino["totals"]

    lineas = [
        _SEP,
        "COMPARACIÓN DE COSTO — mismo consumo, distinto proveedor",
        _SEP,
        "",
        f"Llamadas: {t['calls']}  ·  Tokens de entrada: {t['prompt_tokens']}  ·  "
        f"Tokens de salida: {t['completion_tokens']}",
        "",
        f"{'Agente':<34}{'Modelo':<22}{'Tokens':>8}{'Groq (USD)':>12}{'Destino (USD)':>16}",
        "-" * 92,
    ]
    for grupo, grupo_destino in zip(resumen["by_agent"], con_destino["by_agent"]):
        nombre = grupo["agent_name"] or "(sin agente — PICO/biomarcadores)"
        tokens = grupo["prompt_tokens"] + grupo["completion_tokens"]
        lineas.append(
            f"{nombre:<34}{grupo['model']:<22}{tokens:>8}"
            f"{grupo['cost_usd']:>12.6f}{grupo_destino['cost_usd']:>16.4f}"
        )
    lineas += [
        "-" * 92,
        f"{'TOTAL':<34}{'':<22}"
        f"{t['prompt_tokens'] + t['completion_tokens']:>8}"
        f"{t['cost_usd']:>12.6f}{td['cost_usd']:>16.4f}",
        "",
        "Groq (tier gratuito): USD " + f"{t['cost_usd']:.6f}" + " — es cero por diseño (D5).",
        "Con la arquitectura de destino (Claude Opus / GPT-4o, tarifas de lista "
        f"pública): USD {td['cost_usd']:.4f} este mismo caso.",
        "",
        f"Cuota diaria de Groq: 200.000 tokens. A "
        f"{t['prompt_tokens'] + t['completion_tokens']} tokens por caso, entrarían "
        f"~{200_000 // max(t['prompt_tokens'] + t['completion_tokens'], 1)} casos por día.",
        _SEP,
    ]
    return "\n".join(lineas)


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("DEMO — Telemetría de costos (control de costos, Sprint 4)")
    print(_SEP)

    print("\n[1/2] Mecanismo real en modo mock (sin red, sin gastar cuota)...")
    mecanismo = _correr_mecanismo_real_en_modo_mock()
    (_OUT_DIR / "mecanismo_mock.json").write_text(
        json.dumps(mecanismo, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(f"  Llamadas registradas: {mecanismo['totals']['calls']} "
          f"(todas mock: {mecanismo['totals']['mock_calls']})")
    print("  → output/demo_costos/mecanismo_mock.json")

    print("\n[2/2] Muestra sintética — desglose de tokens y comparación de costo...")
    print("  ADVERTENCIA: son conteos inventados, no una corrida real (ver docstring).")
    muestra = _armar_muestra_sintetica()
    (_OUT_DIR / "muestra_sintetica.json").write_text(
        json.dumps(muestra, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    tabla = _tabla_comparativa(muestra)
    print("\n" + tabla)
    (_OUT_DIR / "comparacion_costos.txt").write_text(tabla, encoding="utf-8")

    # Subproducto de close_registry(): un JSONL que este demo no necesita,
    # los artefactos reales son los .json/.txt de arriba.
    (_OUT_DIR / "_no_usar.jsonl").unlink(missing_ok=True)

    print(f"\nArtefactos en {_OUT_DIR}")
    print(_SEP)


if __name__ == "__main__":
    main()
