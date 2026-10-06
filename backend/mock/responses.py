"""
Respuestas del modo mock, por tarea (control de costos, Sprint 4 — D7).

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


def _cargar_grabadas() -> dict[str, dict[str, Any]]:
    """
    Lee `grabadas.json`: tarea → {response, agent_id, model, seq, recorded_at}.

    Falla fuerte si el archivo falta o está corrupto: sin él el modo mock
    devolvería `{}` para casi todas las tareas y el pipeline degradaría en
    silencio, que es justo lo que este módulo evita.
    """
    datos = json.loads(_ARCHIVO_GRABADAS.read_text(encoding="utf-8"))
    return datos["tasks"]


# Procedencia de cada respuesta grabada (agente, modelo, seq y fecha), para
# auditar de dónde sale cada texto sin abrir el archivo de datos.
RECORDED_RESPONSES: dict[str, dict[str, Any]] = _cargar_grabadas()

# Una entrada por cada tarea de `agents.model_tasks.TASK_BUDGETS`: es lo que
# hace que ninguna llamada del pipeline se quede sin respuesta.
MOCK_RESPONSES: dict[str, str] = {
    tarea: entrada["response"] for tarea, entrada in RECORDED_RESPONSES.items()
}

# JSON válido y vacío: una tarea sin respuesta falla en el parseo de quien
# llama (p. ej. "no devolvió ninguna hipótesis"), de forma controlada, en vez
# de que `call_provider()` reviente por una tarea nueva sin registrar acá.
_SIN_FIXTURE = "{}"


def get_mock_response(task: str) -> str:
    """Respuesta del modo mock para `task`, o un JSON vacío si no hay ninguna."""
    return MOCK_RESPONSES.get(task, _SIN_FIXTURE)
