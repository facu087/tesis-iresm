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

`arbitro_agrupacion` y `agente05_planificacion_terminos` habían bajado a 512 y
1024 con el argumento de que su salida es breve. La medición del 2026-10-04
(tasks.md 4.2) mostró que el argumento no vale para los `gpt-oss`: son modelos
de razonamiento y los tokens de razonamiento cuentan dentro de la salida. Con
nueve hipótesis, la agrupación agotó los 512 con los dos modelos sin llegar a
escribir la respuesta, y la planificación agotó los 1024 en una de tres
llamadas. Cada corte termina en el fallback determinista, es decir, en un
análisis sin agrupamiento. Las dos vuelven al 4096 histórico: el techo es un
límite, no un consumo, así que subirlo no encarece las llamadas que no lo
alcanzan.
"""

from __future__ import annotations

import dataclasses
import os
import sys

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
    "agente06_sintesis",
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

    # ── Salida acotada y validada deterministicamente por código (D6):
    # GROQ_FAST. Una respuesta peor del modelo chico cae en una validación
    # existente (consensus.normalize_partition() / pipeline.trial_matching),
    # nunca en un resultado incorrecto que nadie detecte. ───────────────────
    # Techo histórico: con 512 y 1024 se cortaban por los tokens de
    # razonamiento (ver docstring del módulo).
    "arbitro_agrupacion": TaskBudget(GROQ_FAST, 4096),
    "agente05_planificacion_terminos": TaskBudget(GROQ_FAST, 4096),
    # Hasta MAX_TRIALS=10 ensayos, cada uno con fundamento (hasta 600 chars)
    # y hasta 5 criterios a verificar: el techo histórico no tiene holgura de
    # sobra en el peor caso, así que se conserva sin cambios; solo baja el
    # modelo.
    "agente05_evaluacion_compatibilidad": TaskBudget(GROQ_FAST, 4096),
    "agente06_sintesis": TaskBudget(GROQ_MAIN, 4096),
}


def get_budget(task: str) -> TaskBudget:
    """
    Modelo y techo de tokens que le corresponden a una tarea.

    Levanta `KeyError` ante una tarea no registrada: es un error de
    programación (un sitio de llamada nuevo que no se declaró acá), no una
    condición para degradar en silencio.
    """
    return TASK_BUDGETS[task]


# ── Proveedor por agente (Sprint 5, OpenSpec `multi-proveedor-por-agente`) ──
#
# La arquitectura de la tesis asigna un proveedor a cada agente: Claude Opus a
# los Agentes 01, 04 y 06, GPT-4o al 02 y Gemini Pro al 03. Ese mapa vive acá,
# al lado de `TASK_BUDGETS`, para que "qué usa cada cosa" se revise en un solo
# lugar (design D1). Solo se consulta con `NEXUS_PROVEEDORES=destino` (D2): la
# presencia de una clave sola nunca activa un proveedor pago. Las llamadas que
# no son de un agente del mapa —PICO, biomarcadores, Agente 05— siguen en Groq
# siempre. `call_provider()` (base_agent.py) es quien decide y quien habla con
# el proveedor; este módulo solo describe la asignación.

PROVIDER_GROQ = "groq"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENAI = "openai"
PROVIDER_GOOGLE = "google"

ACTIVATION_ENV = "NEXUS_PROVEEDORES"
MODE_GROQ = "groq"
MODE_TARGET = "destino"

# Modelo por defecto de cada proveedor de destino. Se puede cambiar sin tocar
# el código con la variable de `MODEL_ENV` (design, Open Questions).
# `gemini-3.1-pro-preview` es el Gemini Pro vigente al 2026-11-09.
DEFAULT_MODELS: dict[str, str] = {
    PROVIDER_ANTHROPIC: "claude-opus-5-5",
    PROVIDER_OPENAI: "gpt-4o",
    PROVIDER_GOOGLE: "gemini-3.1-pro-preview",
}

MODEL_ENV: dict[str, str] = {
    PROVIDER_ANTHROPIC: "NEXUS_MODELO_ANTHROPIC",
    PROVIDER_OPENAI: "NEXUS_MODELO_OPENAI",
    PROVIDER_GOOGLE: "NEXUS_MODELO_GOOGLE",
}

API_KEY_ENV: dict[str, str] = {
    PROVIDER_ANTHROPIC: "ANTHROPIC_API_KEY",
    PROVIDER_OPENAI: "OPENAI_API_KEY",
    PROVIDER_GOOGLE: "GOOGLE_API_KEY",
}


@dataclasses.dataclass(frozen=True)
class AgentProvider:
    """
    Proveedor asignado a un agente y techo de sus llamadas.

    `max_tokens=None` conserva el techo de la tarea (`TASK_BUDGETS`). Claude
    Opus y Gemini Pro razonan siempre y el razonamiento cuenta dentro de la
    salida, así que sus llamadas usan 16.000 en lugar de 4.096 para no
    truncar (design D4). GPT-4o no razona: conserva el techo de la tarea.
    """

    provider: str
    max_tokens: int | None


AGENT_PROVIDERS: dict[str, AgentProvider] = {
    "01": AgentProvider(PROVIDER_ANTHROPIC, 16000),
    "02": AgentProvider(PROVIDER_OPENAI, None),
    "03": AgentProvider(PROVIDER_GOOGLE, 16000),
    "04": AgentProvider(PROVIDER_ANTHROPIC, 16000),
    "06": AgentProvider(PROVIDER_ANTHROPIC, 16000),
}


@dataclasses.dataclass(frozen=True)
class ResolvedProvider:
    """Proveedor, modelo y techo con que se hace una llamada de destino."""

    provider: str
    model: str
    max_tokens: int


_avisos_activacion: set[str] = set()


def target_mode_active() -> bool:
    """
    `True` solo si `NEXUS_PROVEEDORES=destino` (sin distinguir mayúsculas).

    Vacía o `groq` es el comportamiento de siempre. Cualquier otro valor avisa
    por stderr una vez por proceso y por valor, y se trata como `groq`: un
    error de tipeo nunca activa un proveedor pago (design D2).
    """
    valor = os.environ.get(ACTIVATION_ENV, "").strip().lower()
    if valor in ("", MODE_GROQ):
        return False
    if valor == MODE_TARGET:
        return True
    if valor not in _avisos_activacion:
        _avisos_activacion.add(valor)
        print(
            f"[NEXUS] {ACTIVATION_ENV}={valor!r} no es un valor reconocido "
            f"({MODE_GROQ!r} o {MODE_TARGET!r}); se usa Groq para todo.",
            file=sys.stderr,
        )
    return False


def model_for(provider: str) -> str:
    """Modelo configurado para un proveedor de destino."""
    override = os.environ.get(MODEL_ENV[provider], "").strip()
    return override or DEFAULT_MODELS[provider]


def resolve_agent_provider(agent_id: str | None, task: str) -> ResolvedProvider | None:
    """
    Proveedor de destino que le corresponde a esta llamada, o `None` si va a
    Groq.

    Devuelve `None` sin la arquitectura de destino activa, sin `agent_id`
    (PICO, biomarcadores) o con un agente fuera del mapa (Agente 05). No mira
    si la clave está configurada: eso lo decide `call_provider()`, que es
    quien registra el respaldo.
    """
    if agent_id is None or not target_mode_active():
        return None
    asignado = AGENT_PROVIDERS.get(agent_id)
    if asignado is None:
        return None
    techo = asignado.max_tokens or get_budget(task).max_tokens
    return ResolvedProvider(asignado.provider, model_for(asignado.provider), techo)
