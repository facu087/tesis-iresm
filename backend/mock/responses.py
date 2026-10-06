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

Regla de elección: con varias grabaciones para una misma tarea (críticas,
revisiones y recitaciones: una o dos por agente) se toma la primera por orden de
llamada (`seq` más bajo). En modo mock los tres agentes reciben la misma
respuesta para una tarea compartida, así que el número y el orden de las
hipótesis de una corrida mock no coinciden con los de la corrida real: lo que
cita posiciones (grupos del Árbitro, veredictos, números de recitación,
candidatas del Agente 05) se aplica por posición a las hipótesis de la corrida
mock, y lo que cita ensayos o artículos de ClinicalTrials.gov y PubMed solo
sobrevive si esas consultas devuelven lo mismo que el día de la grabación. El
modo mock no toca la red para el LLM, pero conserva las consultas externas.
Una respuesta grabada solo se usa si atraviesa el parseo real sin descartarse
ni caer en el fallback (`tests/test_mock_responses.py`).

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

import json
from pathlib import Path
from typing import Any

_ARCHIVO_GRABADAS = Path(__file__).with_name("grabadas.json")

# Caché de la primera lectura exitosa: tarea → entrada grabada. `None` mientras
# no se haya pedido nada; un fallo de carga no deja nada a medias acá.
_CACHE: dict[str, dict[str, Any]] | None = None

# JSON válido y vacío: una tarea sin respuesta falla en el parseo de quien
# llama (p. ej. "no devolvió ninguna hipótesis"), de forma controlada, en vez
# de que `call_provider()` reviente por una tarea nueva sin registrar acá.
_SIN_FIXTURE = "{}"


class RespuestasGrabadasInvalidas(RuntimeError):
    """`grabadas.json` falta, no es JSON válido o no tiene la estructura esperada."""


def _cargar_grabadas() -> dict[str, dict[str, Any]]:
    """
    Lee y valida `grabadas.json`: tarea → {response, agent_id, model, seq, recorded_at}.

    Falla fuerte con `RespuestasGrabadasInvalidas` si el archivo falta, no es
    JSON, no tiene un objeto `tasks` o alguna entrada no trae una `response`
    de texto no vacío: sin él el modo mock devolvería `{}` para casi todas las
    tareas y el pipeline degradaría en silencio, que es justo lo que este
    módulo evita. El mensaje nombra el archivo y el defecto, nunca su contenido.
    """
    nombre = _ARCHIVO_GRABADAS.name

    def _falla(motivo: str) -> RespuestasGrabadasInvalidas:
        return RespuestasGrabadasInvalidas(
            f"No se pueden usar las respuestas del modo mock ({nombre}): {motivo}."
        )

    try:
        crudo = _ARCHIVO_GRABADAS.read_text(encoding="utf-8")
    except OSError as exc:
        raise _falla(f"no se pudo leer el archivo ({type(exc).__name__})") from exc
    try:
        datos = json.loads(crudo)
    except ValueError as exc:
        raise _falla("no es JSON válido") from exc

    tareas = datos.get("tasks") if isinstance(datos, dict) else None
    if not isinstance(tareas, dict):
        raise _falla("falta el objeto `tasks`")
    for tarea, entrada in tareas.items():
        respuesta = entrada.get("response") if isinstance(entrada, dict) else None
        if not isinstance(respuesta, str) or not respuesta.strip():
            raise _falla(f"la tarea `{tarea}` no tiene una `response` de texto no vacío")
    return tareas


def get_recorded_responses() -> dict[str, dict[str, Any]]:
    """
    Procedencia de cada respuesta grabada (agente, modelo, seq y fecha), para
    auditar de dónde sale cada texto sin abrir el archivo de datos.

    Lee el archivo la primera vez y reutiliza el resultado después.
    """
    global _CACHE
    if _CACHE is None:
        _CACHE = _cargar_grabadas()
    return _CACHE


def get_mock_responses() -> dict[str, str]:
    """Una respuesta por tarea de `agents.model_tasks.TASK_BUDGETS`, en texto."""
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


def get_mock_response(task: str) -> str:
    """Respuesta del modo mock para `task`, o un JSON vacío si no hay ninguna."""
    entrada = get_recorded_responses().get(task)
    return entrada["response"] if entrada is not None else _SIN_FIXTURE
