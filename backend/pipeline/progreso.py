"""
Avance del pipeline: qué paso está corriendo, para quien quiera escucharlo.

`POST /api/analyze/stream` abre un destino antes de correr el pipeline y cada
etapa avisa cuando empieza. Sin destino abierto (`POST /api/analyze`, los
scripts, los tests) avisar no hace nada: el pipeline no sabe si alguien escucha.

Se basa en `contextvars`, como `backend/telemetry/usage.py`: dos análisis
concurrentes no mezclan sus avisos, y las tareas que el pipeline lanza con
`asyncio.gather()` heredan el destino del análisis que las creó.

Un evento lleva solo identificadores (el número de paso o de ronda): nunca
texto clínico, prompts ni respuestas del modelo.
"""

from __future__ import annotations

import contextvars
import sys
from collections.abc import Callable

Destino = Callable[[dict], None]

_destino: contextvars.ContextVar[Destino | None] = contextvars.ContextVar(
    "nexus_progreso", default=None
)


def abrir(destino: Destino) -> contextvars.Token:
    """Registra quién recibe los avisos del análisis en curso."""
    return _destino.set(destino)


def cerrar(token: contextvars.Token) -> None:
    """Deja de entregar avisos. Va en el `finally` de quien llamó a `abrir()`."""
    _destino.reset(token)


def paso(paso_id: str) -> None:
    """Avisa que empezó un paso del pipeline (`"01"` a `"08"`)."""
    _emitir({"evento": "paso", "paso": paso_id})


def ronda(numero: int) -> None:
    """Avisa que empezó una ronda del debate (2, 3 o 4)."""
    _emitir({"evento": "ronda", "ronda": numero})


def _emitir(evento: dict) -> None:
    destino = _destino.get()
    if destino is None:
        return
    try:
        destino(evento)
    except Exception as exc:
        # El avance es accesorio: un destino roto no puede tirar el análisis.
        # Solo el tipo de la excepción, nunca su mensaje.
        print(
            f"[NEXUS] No se pudo entregar un aviso de avance ({type(exc).__name__}).",
            file=sys.stderr,
        )
