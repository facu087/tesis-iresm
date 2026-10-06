"""
Respuestas del modo mock, por tarea (control de costos, Sprint 4 — D7).

El archivo de datos se carga de forma diferida: importar este módulo (y, por
lo tanto, `backend.agents.base_agent`) no lo lee. Se lee una sola vez, la
primera vez que se pide una respuesta o los datos grabados, de modo que la
operación real (sin modo mock) nunca lo toca. Si en modo mock falta o está
mal formado, falla fuerte con `RespuestasGrabadasInvalidas`.

Cada respuesta atraviesa el mismo parseo y las mismas validaciones que una
respuesta real (D7: "el modo mock ejercita el flujo real").

**Origen de las respuestas (tasks.md, tarea 6.2).** Todas salen de una corrida real
contra Groq hecha el 2026-10-06 con `scripts/medir_costos.py --grabar` (modelo
`openai/gpt-oss-120b`, y `openai/gpt-oss-20b` para agrupación y Agente 05, como
fija `TASK_BUDGETS`).
Están en `backend/mock/grabadas.json` **tal como las devolvió el modelo**: sin
retocar, con su sangría, su orden de claves y sus rarezas. Esa fidelidad es lo
que hace que el modo mock se parezca a lo que el modelo devuelve de verdad. El
caso es el de prueba anonimizado del proyecto (neuropatía axonal
sensitivomotora, paciente masculino de 42 años).

Regla de elección: en el archivo, una tarea tiene una sola entrada o una lista de
entradas, cada una con el agente que la produjo (`agent_id`, nulo si la llamada
no vino de un agente: PICO y biomarcadores) y su orden de llamada en la corrida
(`seq`). Para una llamada de la tarea T hecha por el agente A:

  - las candidatas son las entradas de T cuyo `agent_id` es A, por `seq`;
  - se devuelve la candidata número n, donde n es cuántas veces ya se pidió
    (T, A) en el análisis en curso; pasado el final, se repite la última;
  - si A no tiene ninguna entrada para T, se devuelve la primera de T por `seq`.

Así las revisiones de las Rondas 3 y 4 de un agente reciben, en ese orden, las
dos que ese agente produjo en la corrida real, y cada agente recibe su crítica y
su recitación. El conteo n vive en una sesión de reproducción por análisis
(`open_replay_session()` / `close_replay_session()`), que se abre donde se abre
el registro de consumo: dos análisis seguidos reciben la misma secuencia. Sin
una sesión abierta la elección no guarda estado y n vale siempre 0.

El orden de las llamadas de un mismo (T, A) es reproducible porque el pipeline
nunca las hace a la vez: las rondas del debate se esperan una a una y, dentro de
una ronda, cada agente llama una sola vez. Las llamadas simultáneas son siempre
de agentes o de tareas distintas, que cuentan por separado.

**El archivo versionado todavía tiene una entrada por tarea** (la primera por
`seq`): la grabación completa de la corrida no se conservó. Con él vale el último
caso de la regla, que es el comportamiento anterior: los tres agentes reciben la
misma respuesta para una tarea compartida, así que el número y el orden de las
hipótesis de una corrida mock no coinciden con los de la corrida real. Lo que
cita posiciones (grupos del Árbitro, veredictos, números de recitación,
candidatas del Agente 05) se aplica por posición a las hipótesis de la corrida
mock, y lo que cita ensayos o artículos de ClinicalTrials.gov y PubMed solo
sobrevive si esas consultas devuelven lo mismo que el día de la grabación. Un
archivo con todas las entradas se genera desde el `grabacion.json` de una corrida
real con `scripts/regenerar_mock.py` (`backend/mock/regenerar.py`).

El modo mock no toca la red para el LLM, pero conserva las consultas externas.
Una respuesta grabada solo se usa si atraviesa el parseo real sin descartarse
ni caer en el fallback (`tests/test_mock_responses.py`, que recorre todas las
entradas de cada tarea y no solo la primera).

**Las doce tareas son grabaciones.** `debate_critica` tardó en serlo: las
críticas reales nombran a su destinatario como "Agent 02", "Agent01" o
"Agent03", y `debate._critiques_for()` compara `target_agent_id` contra el ID del
agente ("01", "02", "03"), así que ninguna llegaba a su destinatario y por eso se
había escrito una a mano. Desde que `BaseAgent._parse_critiques()` normaliza el
destinatario a su ID canónico (commit `a2227ae`) esa razón desapareció y la
crítica sale también de la corrida real. Detalle en
`odd/tasks/grabacion-respuestas-mock.md`.
"""

from __future__ import annotations

import contextvars
import json
import threading
from pathlib import Path
from typing import Any

_ARCHIVO_GRABADAS = Path(__file__).with_name("grabadas.json")

# Caché de la primera lectura exitosa: tarea → entradas grabadas, por `seq`.
# `None` mientras no se haya pedido nada; un fallo de carga no deja nada a
# medias acá.
_CACHE: dict[str, list[dict[str, Any]]] | None = None

# JSON válido y vacío: una tarea sin respuesta falla en el parseo de quien
# llama (p. ej. "no devolvió ninguna hipótesis"), de forma controlada, en vez
# de que `call_provider()` reviente por una tarea nueva sin registrar acá.
_SIN_FIXTURE = "{}"


class RespuestasGrabadasInvalidas(RuntimeError):
    """`grabadas.json` falta, no es JSON válido o no tiene la estructura esperada."""


# ── Carga y validación del archivo de datos ───────────────────────────────────

def _falla(nombre: str, motivo: str) -> RespuestasGrabadasInvalidas:
    """Error de carga: nombra el archivo y el defecto, nunca su contenido."""
    return RespuestasGrabadasInvalidas(
        f"No se pueden usar las respuestas del modo mock ({nombre}): {motivo}."
    )


def _tiene_respuesta(entrada: object) -> bool:
    """Indica si `entrada` es un objeto con una `response` de texto no vacío."""
    respuesta = entrada.get("response") if isinstance(entrada, dict) else None
    return isinstance(respuesta, str) and bool(respuesta.strip())


def validar_grabadas(datos: object, nombre: str) -> dict[str, list[dict[str, Any]]]:
    """
    Valida el contenido ya decodificado de un archivo de respuestas grabadas y
    lo devuelve como tarea → lista de entradas ordenadas por `seq`.

    Es la única validación del formato: la usa el cargador y la usa el
    generador (`backend/mock/regenerar.py`) antes de escribir, para no dejar en
    disco un archivo que después no se pueda cargar. `nombre` identifica el
    archivo en el mensaje de error, que nunca incluye su contenido.

    `tasks[<tarea>]` puede ser:

      - un objeto: la única entrada de la tarea. Solo se le exige una
        `response` de texto no vacío, como hasta ahora;
      - una lista no vacía de entradas. Como entre ellas se elige por agente y
        por orden de llamada, cada una debe traer además `agent_id` (texto o
        nulo) y un `seq` entero que no se repita dentro de la tarea.
    """
    tareas = datos.get("tasks") if isinstance(datos, dict) else None
    if not isinstance(tareas, dict):
        raise _falla(nombre, "falta el objeto `tasks`")

    validadas: dict[str, list[dict[str, Any]]] = {}
    for tarea, contenido in tareas.items():
        if not isinstance(contenido, list):
            if not _tiene_respuesta(contenido):
                raise _falla(
                    nombre, f"la tarea `{tarea}` no tiene una `response` de texto no vacío"
                )
            validadas[tarea] = [contenido]
            continue

        if not contenido:
            raise _falla(nombre, f"la tarea `{tarea}` tiene una lista de entradas vacía")
        vistos: set[int] = set()
        for posicion, entrada in enumerate(contenido, start=1):
            donde = f"la entrada {posicion} de la tarea `{tarea}`"
            if not _tiene_respuesta(entrada):
                raise _falla(nombre, f"{donde} no tiene una `response` de texto no vacío")
            seq = entrada.get("seq")
            # `bool` es subclase de `int`: un `true` no es un número de llamada.
            if not isinstance(seq, int) or isinstance(seq, bool):
                raise _falla(nombre, f"{donde} no tiene un `seq` entero")
            if seq in vistos:
                raise _falla(nombre, f"{donde} repite el `seq` {seq}")
            vistos.add(seq)
            if "agent_id" not in entrada or not isinstance(entrada["agent_id"], str | None):
                raise _falla(nombre, f"{donde} no tiene un `agent_id` de texto o nulo")
        validadas[tarea] = sorted(contenido, key=lambda entrada: entrada["seq"])
    return validadas


def _cargar_grabadas() -> dict[str, list[dict[str, Any]]]:
    """
    Lee y valida `grabadas.json`: tarea → entradas {response, agent_id, model,
    seq, recorded_at}, ordenadas por `seq`.

    Falla fuerte con `RespuestasGrabadasInvalidas` si el archivo falta, no es
    JSON o no pasa `validar_grabadas()`: sin él el modo mock devolvería `{}`
    para casi todas las tareas y el pipeline degradaría en silencio, que es
    justo lo que este módulo evita. El mensaje nombra el archivo y el defecto,
    nunca su contenido.
    """
    nombre = _ARCHIVO_GRABADAS.name
    try:
        crudo = _ARCHIVO_GRABADAS.read_text(encoding="utf-8")
    except OSError as exc:
        raise _falla(nombre, f"no se pudo leer el archivo ({type(exc).__name__})") from exc
    try:
        datos = json.loads(crudo)
    except ValueError as exc:
        raise _falla(nombre, "no es JSON válido") from exc
    return validar_grabadas(datos, nombre)


def get_recorded_entries() -> dict[str, list[dict[str, Any]]]:
    """
    Todas las entradas grabadas de cada tarea, ordenadas por `seq`.

    Lee el archivo la primera vez y reutiliza el resultado después.
    """
    global _CACHE
    if _CACHE is None:
        _CACHE = _cargar_grabadas()
    return _CACHE


def get_recorded_responses() -> dict[str, dict[str, Any]]:
    """
    Procedencia de la primera respuesta grabada de cada tarea (agente, modelo,
    seq y fecha), para auditar de dónde sale cada texto sin abrir el archivo de
    datos. Con una entrada por tarea es la tarea completa; para ver todas las
    de un archivo con varias, `get_recorded_entries()`.
    """
    return {tarea: entradas[0] for tarea, entradas in get_recorded_entries().items()}


def get_mock_responses() -> dict[str, str]:
    """
    Una respuesta por tarea de `agents.model_tasks.TASK_BUDGETS`, en texto: la
    primera por `seq`, que es la que recibe una llamada sin agente ni sesión.
    """
    return {
        tarea: entrada["response"]
        for tarea, entrada in get_recorded_responses().items()
    }


def __getattr__(nombre: str) -> Any:
    """
    Mantiene los nombres `RECORDED_RESPONSES` y `MOCK_RESPONSES` del módulo sin
    cargarlos al importar (los tests y quien los consulte siguen igual).
    """
    if nombre == "RECORDED_RESPONSES":
        return get_recorded_responses()
    if nombre == "MOCK_RESPONSES":
        return get_mock_responses()
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")


# ── Sesión de reproducción por análisis ───────────────────────────────────────

class ReplaySession:
    """
    Cuántas veces se pidió cada (tarea, agente) en un análisis en modo mock.

    Sigue el patrón del registro de consumo (`backend/telemetry/usage.py`): un
    objeto por análisis, activo en un contexto (`contextvars`). Tiene que
    crearse en el contexto del análisis **antes** de que el pipeline reparta el
    trabajo: cada tarea de `asyncio.gather()` y cada `asyncio.to_thread()`
    recibe una copia del contexto, y todas las copias apuntan a este mismo
    objeto. Un contador creado recién en la primera llamada quedaría en la
    copia de quien lo creó y los demás no lo verían.

    `next_turn()` tiene su propio lock: las llamadas llegan desde threads del
    sistema operativo, no solo desde corrutinas del mismo hilo.
    """

    def __init__(self) -> None:
        self._turnos: dict[tuple[str, str | None], int] = {}
        self._lock = threading.Lock()

    def next_turn(self, task: str, agent_id: str | None) -> int:
        """Devuelve cuántas veces se pidió ya (tarea, agente) y cuenta este pedido."""
        clave = (task, agent_id)
        with self._lock:
            turno = self._turnos.get(clave, 0)
            self._turnos[clave] = turno + 1
            return turno


_sesion: contextvars.ContextVar[ReplaySession | None] = contextvars.ContextVar(
    "nexus_mock_replay_session", default=None
)


def open_replay_session() -> contextvars.Token:
    """
    Abre una sesión de reproducción nueva y la activa en el contexto actual.

    La llama quien conoce el ciclo de vida de un análisis (el router, un
    script), en el mismo lugar donde abre el registro de consumo. Devuelve el
    token que hay que pasarle a `close_replay_session()`. No lee el archivo de
    datos: fuera del modo mock nadie consulta la sesión y abrirla no cuesta nada.
    """
    return _sesion.set(ReplaySession())


def current_replay_session() -> ReplaySession | None:
    """Sesión de reproducción activa en el contexto actual, o `None` si no hay."""
    return _sesion.get()


def close_replay_session(token: contextvars.Token) -> None:
    """Cierra la sesión activa y restaura la que hubiera antes de abrirla."""
    _sesion.reset(token)


# ── Elección de la respuesta ──────────────────────────────────────────────────

def get_mock_response(task: str, *, agent_id: str | None = None) -> str:
    """
    Respuesta del modo mock para una llamada de `task` hecha por `agent_id`
    (`None` si no viene de un agente), o un JSON vacío si la tarea no tiene
    ninguna grabada.

    Aplica la regla de elección del encabezado del módulo. Dentro de una
    sesión de reproducción cada pedido cuenta; sin sesión se comporta como el
    primer pedido de (tarea, agente), sin guardar estado.
    """
    entradas = get_recorded_entries().get(task)
    if not entradas:
        return _SIN_FIXTURE

    sesion = _sesion.get()
    turno = sesion.next_turn(task, agent_id) if sesion is not None else 0

    propias = [entrada for entrada in entradas if entrada.get("agent_id") == agent_id]
    if not propias:
        # El agente no tiene grabación para esta tarea: la primera de la tarea.
        return entradas[0]["response"]
    return propias[min(turno, len(propias) - 1)]["response"]
