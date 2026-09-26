"""
Mapa tarea → (modelo, techo de tokens) para cada llamada al LLM del pipeline
(control de costos, Sprint 4 — D6).

Antes de este cambio, `max_tokens=4096` era fijo para toda llamada
(`BaseAgent._call_llm()`), sin importar la tarea: la agrupación del Árbitro
devuelve `{"groups": [[1,3],[2]]}` —unas decenas de tokens— y reservaba lo
mismo que un razonamiento clínico completo. Ahora cada sitio de llamada
declara su tarea (el parámetro `task` de `_call_llm()`/`call_provider()`), y
el techo y el modelo se consultan acá: revisar "qué usa cada cosa" no obliga
a recorrer los agentes, y ajustar la política —por ejemplo, revertir una
tarea al modelo grande— es cambiar una línea en `TASK_BUDGETS`.

`GROQ_MAIN`/`GROQ_FAST` viven acá, no en `base_agent.py`: es al revés,
`base_agent.py` los importa de acá para no crear un import circular (este
módulo no depende de `agents.base_agent`).

Los techos de `pico_sintesis` y `biomarcadores_extraccion` conservan los
valores que ya tenían sus módulos antes de este cambio: no hay evidencia de
que necesiten ajuste, y "techo con holgura" no es "achicar todo lo que se
pueda" (spec `presupuesto-por-tarea`). Las tareas de razonamiento clínico
(generación de hipótesis, crítica, revisión, recitación, veredictos)
conservan el 4096 histórico por la misma razón: no hay una corrida real que
mida cuánto necesitan de verdad (queda pendiente, ver tasks.md 4.2), y
reducirlas a ciegas arriesga truncar una respuesta válida, que la spec trata
como un defecto, no un ahorro.

`arbitro_agrupacion` es la excepción con evidencia clara: su salida son solo
índices (`{"groups": [[1,3],[2]]}`), así que un techo bajo tiene holgura de
sobra sin importar cuántas hipótesis se agrupen.
"""

from __future__ import annotations

import dataclasses

# Modelos disponibles.
GROQ_MAIN = "openai/gpt-oss-120b"  # Razonamiento clínico
GROQ_FAST = "openai/gpt-oss-20b"   # Tareas de salida acotada y validada por código


@dataclasses.dataclass(frozen=True)
class TaskBudget:
    """Modelo y techo de tokens que le corresponden a una tarea."""

    model: str
    max_tokens: int


# Tareas cuya calidad determina la del análisis: generación de hipótesis,
# crítica cruzada, revisiones del debate, recitación, veredictos del Árbitro y
# síntesis PICO. MUST NOT usar el modelo rápido (requisito "El razonamiento
# clínico no se degrada", spec `presupuesto-por-tarea`). El test de inventario
# (tasks.md 5.5) recorre este conjunto.
REASONING_TASKS: frozenset[str] = frozenset({
    "agente01_hipotesis",
    "agente02_hipotesis",
    "agente03_hipotesis",
    "debate_critica",
    "debate_revision",
    "debate_recitacion",
    "arbitro_veredictos",
    "pico_sintesis",
})

TASK_BUDGETS: dict[str, TaskBudget] = {
    # ── Razonamiento clínico — GROQ_MAIN, techo histórico sin evidencia para
    # bajarlo (ver docstring del módulo). ──────────────────────────────────
    "agente01_hipotesis": TaskBudget(GROQ_MAIN, 4096),
    "agente02_hipotesis": TaskBudget(GROQ_MAIN, 4096),
    "agente03_hipotesis": TaskBudget(GROQ_MAIN, 4096),
    "debate_critica": TaskBudget(GROQ_MAIN, 4096),
    "debate_revision": TaskBudget(GROQ_MAIN, 4096),
    "debate_recitacion": TaskBudget(GROQ_MAIN, 4096),
    "arbitro_veredictos": TaskBudget(GROQ_MAIN, 4096),
    "pico_sintesis": TaskBudget(GROQ_MAIN, 2048),          # techo original de pico.py
    "biomarcadores_extraccion": TaskBudget(GROQ_MAIN, 1024),  # techo original del extractor

    # ── Salida acotada y validada deterministicamente por código (D6). Acá
    # arranca en GROQ_MAIN: el modelo por tarea se decide en la sección 5. ──
    "arbitro_agrupacion": TaskBudget(GROQ_MAIN, 512),
    "agente05_planificacion_terminos": TaskBudget(GROQ_MAIN, 1024),
    # Hasta MAX_TRIALS=10 ensayos, cada uno con fundamento (hasta 600 chars)
    # y hasta 5 criterios a verificar: el techo histórico no tiene holgura de
    # sobra en el peor caso, así que se conserva sin cambios.
    "agente05_evaluacion_compatibilidad": TaskBudget(GROQ_MAIN, 4096),
}


def get_budget(task: str) -> TaskBudget:
    """
    Modelo y techo de tokens que le corresponden a una tarea.

    Levanta `KeyError` ante una tarea no registrada: es un error de
    programación (un sitio de llamada nuevo que no se declaró acá), no una
    condición para degradar en silencio.
    """
    return TASK_BUDGETS[task]
