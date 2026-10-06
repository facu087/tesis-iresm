"""
Grabador de las respuestas crudas del modelo (control de costos, Sprint 4).

Las respuestas del modo mock (`backend/mock/responses.py`) están escritas a
mano porque nada guardaba el texto que devuelve el modelo: la telemetría
(`backend/telemetry/usage.py`) solo conserva conteos. Este módulo cubre esa
falta para que UNA corrida real contra el proveedor deje en disco lo necesario
para regenerar las respuestas grabadas.

Sigue el mismo patrón que la telemetría: el grabador vive en un contexto
(`contextvars`), se abre y se cierra de forma explícita y, sin uno abierto, no
hace nada. El contexto se propaga solo a las corrutinas hijas y a los
`asyncio.to_thread()` que usa el pipeline.

Reglas de diseño:

  - **Apagado salvo que un script lo abra.** No hay variable de entorno que lo
    active y `api/router.py` no lo abre: un análisis servido por la API nunca
    persiste respuestas del modelo, que pueden contener texto clínico.
  - **Solo la respuesta del modelo.** `record_response()` no recibe el prompt de
    sistema ni el mensaje del usuario, así que estructuralmente no puede
    guardarlos.
  - **Nunca rompe el pipeline.** Un fallo al escribir el archivo se avisa por
    stderr, sin el texto de ninguna respuesta, y no se propaga.
"""

from __future__ import annotations

import contextvars
import dataclasses
import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path


class ResponseRecorder:
    """
    Entradas grabadas de una corrida, en el orden en que se hicieron las llamadas.

    `record()` tiene su propio lock: el pipeline llama en paralelo desde varios
    `asyncio.to_thread()`, que corren en threads del sistema operativo.
    """

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self._lock = threading.Lock()

    def record(self, entry: dict) -> None:
        """Agrega una entrada y le asigna su número de secuencia (desde 1)."""
        with self._lock:
            self.entries.append({"seq": len(self.entries) + 1, **entry})


_current: contextvars.ContextVar[ResponseRecorder | None] = contextvars.ContextVar(
    "nexus_response_recorder", default=None
)


def open_recorder() -> contextvars.Token:
    """
    Abre un grabador nuevo y lo activa en el contexto actual.

    Solo lo llama un script. Devuelve el token que hay que pasarle a
    `close_recorder()` para cerrarlo.
    """
    return _current.set(ResponseRecorder())


def current() -> ResponseRecorder | None:
    """Grabador activo en el contexto actual, o `None` si no hay ninguno."""
    return _current.get()


def record_response(
    *,
    task: str,
    model: str,
    agent_id: str | None,
    agent_name: str | None,
    truncated: bool,
    response: str,
) -> None:
    """
    Registra la respuesta cruda de una llamada exitosa al proveedor.

    No hace nada si no hay un grabador abierto: un test, un script de demo o un
    análisis servido por la API llaman a `call_provider()` sin pasar por acá.
    `truncated` indica que la respuesta se cortó al alcanzar el techo de tokens.
    """
    grabador = _current.get()
    if grabador is None:
        return
    grabador.record({
        "task": task,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "model": model,
        "truncated": truncated,
        "response": response,
    })


def close_recorder(
    token: contextvars.Token,
    *,
    output_path: Path | str,
) -> list[dict] | None:
    """
    Cierra el grabador activo y escribe sus entradas en `output_path`.

    Devuelve las entradas grabadas, o `None` si no había un grabador activo
    (nada que cerrar). El archivo es JSON en UTF-8, con `ensure_ascii=False` e
    indentado, con las claves `generated_at` y `entries`. Un fallo al escribirlo
    (permisos, disco lleno, ruta inexistente) nunca se propaga: se avisa por
    stderr, sin ningún texto de respuesta, y las entradas se devuelven igual.
    """
    grabador = _current.get()
    _current.reset(token)
    if grabador is None:
        return None

    entradas = list(grabador.entries)
    contenido = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entries": entradas,
    }
    destino = Path(output_path)
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        print(
            f"[NEXUS] grabador: no se pudo escribir la grabación de "
            f"{len(entradas)} respuesta(s) ({type(exc).__name__}).",
            file=sys.stderr,
        )
    return entradas
