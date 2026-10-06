"""
Generador del archivo de respuestas del modo mock a partir de una grabación.

`scripts/medir_costos.py --grabar` deja en `grabacion.json` la respuesta cruda
de cada llamada de una corrida real, en orden (`backend/mock/recorder.py`):

    {"generated_at": "...", "entries": [
        {"seq", "task", "agent_id", "agent_name", "model", "truncated", "response"}, ...
    ]}

Este módulo la convierte en un archivo con la forma de `grabadas.json`, con
**todas** las entradas de cada tarea y no solo la primera, que es lo que le
permite al modo mock entregar a cada agente su respuesta de cada ronda
(`backend/mock/responses.py`, regla de elección).

Reglas de diseño:

  - **El texto de la respuesta no se toca.** Se copia tal como lo devolvió el
    modelo; lo único que se agrega es la fecha de la grabación.
  - **Nunca escribe un archivo que el cargador rechazaría.** Antes de escribir,
    el resultado pasa por la misma validación que aplica el cargador
    (`responses.validar_grabadas()`).
  - **No tiene destino por defecto.** Quien llama indica dónde escribir: este
    módulo nunca pisa `backend/mock/grabadas.json` por su cuenta.
  - **Los errores no arrastran texto de respuestas**, que puede ser texto del
    caso: nombran la entrada y el defecto.

Lo que este módulo no puede comprobar es que cada respuesta atraviese el parseo
real de su sitio de llamada: eso lo verifica `tests/test_mock_responses.py`
sobre el archivo versionado, y hay que correrlo después de reemplazarlo.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import responses

_DESCRIPCION = (
    "Respuestas crudas del modelo grabadas de una corrida real "
    "(scripts/medir_costos.py --grabar): todas las de cada tarea, en orden de "
    "llamada (seq), con el agente que produjo cada una. El texto de 'response' "
    "es el que devolvio el modelo, sin retocar."
)


class GrabacionInvalida(ValueError):
    """La grabación de origen falta, no es JSON válido o no tiene la forma esperada."""


class DestinoNoEscribible(RuntimeError):
    """El archivo de destino no se pudo escribir; lo que había queda como estaba."""


def _fecha(grabacion: dict[str, Any], recorded_at: str | None) -> str:
    """
    Fecha de la grabación (`AAAA-MM-DD`): la indicada o la de `generated_at`.

    Se valida en los dos casos, para que el archivo generado no lleve como
    procedencia un texto que no es una fecha.
    """
    if recorded_at is not None:
        try:
            return date.fromisoformat(recorded_at).isoformat()
        except (TypeError, ValueError) as exc:
            raise GrabacionInvalida("la fecha indicada no tiene la forma AAAA-MM-DD") from exc

    generado = grabacion.get("generated_at")
    if not isinstance(generado, str):
        raise GrabacionInvalida(
            "la grabación no trae `generated_at` y no se indicó la fecha de la corrida"
        )
    try:
        return datetime.fromisoformat(generado).date().isoformat()
    except ValueError as exc:
        raise GrabacionInvalida("`generated_at` no es una fecha ISO 8601") from exc


def _validar_entrada(entrada: object, posicion: int, vistos: set[int]) -> dict[str, Any]:
    """Comprueba una entrada de la grabación; el error la nombra por posición."""
    donde = f"la entrada {posicion} de la grabación"
    if not isinstance(entrada, dict):
        raise GrabacionInvalida(f"{donde} no es un objeto")

    tarea = entrada.get("task")
    if not isinstance(tarea, str) or not tarea.strip():
        raise GrabacionInvalida(f"{donde} no tiene una `task` de texto no vacío")
    seq = entrada.get("seq")
    # `bool` es subclase de `int`: un `true` no es un número de llamada.
    if not isinstance(seq, int) or isinstance(seq, bool):
        raise GrabacionInvalida(f"{donde} no tiene un `seq` entero")
    if seq in vistos:
        raise GrabacionInvalida(f"{donde} repite el `seq` {seq}")
    vistos.add(seq)
    respuesta = entrada.get("response")
    if not isinstance(respuesta, str) or not respuesta.strip():
        raise GrabacionInvalida(f"{donde} no tiene una `response` de texto no vacío")
    if not isinstance(entrada.get("model"), str) or not entrada["model"].strip():
        raise GrabacionInvalida(f"{donde} no tiene un `model` de texto no vacío")
    if "agent_id" not in entrada or not isinstance(entrada["agent_id"], str | None):
        raise GrabacionInvalida(f"{donde} no tiene un `agent_id` de texto o nulo")
    return entrada


def construir_grabadas(
    grabacion: object, *, recorded_at: str | None = None
) -> dict[str, Any]:
    """
    Convierte el contenido de un `grabacion.json` en el de un `grabadas.json`.

    Conserva todas las entradas, agrupadas por tarea y ordenadas por `seq`. Las
    tareas quedan en orden alfabético, como en el archivo versionado, para que
    regenerarlo produzca un diff legible. No modifica `grabacion`.

    Args:
        grabacion:   Contenido ya decodificado de la grabación.
        recorded_at: Fecha de la corrida (`AAAA-MM-DD`). Si se omite, se toma
                     de `generated_at`.

    Raises:
        GrabacionInvalida: si la grabación no tiene la forma esperada.
    """
    if not isinstance(grabacion, dict):
        raise GrabacionInvalida("la grabación no es un objeto JSON")
    entradas = grabacion.get("entries")
    if not isinstance(entradas, list) or not entradas:
        raise GrabacionInvalida("la grabación no tiene una lista `entries` con entradas")
    fecha = _fecha(grabacion, recorded_at)

    vistos: set[int] = set()
    por_tarea: dict[str, list[dict[str, Any]]] = {}
    for posicion, cruda in enumerate(entradas, start=1):
        entrada = _validar_entrada(cruda, posicion, vistos)
        por_tarea.setdefault(entrada["task"], []).append({
            "agent_id": entrada["agent_id"],
            "model": entrada["model"],
            "seq": entrada["seq"],
            "recorded_at": fecha,
            "response": entrada["response"],
        })

    return {
        "description": _DESCRIPCION,
        "recorded_at": fecha,
        "tasks": {
            tarea: sorted(por_tarea[tarea], key=lambda entrada: entrada["seq"])
            for tarea in sorted(por_tarea)
        },
    }


def regenerar_archivo(
    origen: Path | str, destino: Path | str, *, recorded_at: str | None = None
) -> dict[str, int]:
    """
    Lee la grabación de `origen` y escribe en `destino` el archivo de respuestas.

    El resultado se valida con `responses.validar_grabadas()` antes de abrir el
    destino: si la grabación o el resultado no son válidos no se escribe nada y
    lo que hubiera en `destino` queda como estaba. El archivo se escribe en
    UTF-8, sin escapes (`ensure_ascii=False`) e indentado, como el versionado.

    Returns:
        Conteos para informar: `tasks`, `entries` y `truncated` (respuestas que
        el modelo cortó al alcanzar el techo de tokens, que conviene revisar
        porque difícilmente atraviesen el parseo).

    Raises:
        GrabacionInvalida: si `origen` no se puede leer, no es JSON o no tiene
                           la forma esperada.
        RespuestasGrabadasInvalidas: si el resultado no pasa la validación del
                           cargador.
        DestinoNoEscribible: si el destino no se puede escribir (sin permiso,
                           disco lleno, es una carpeta). El destino no cambia.
    """
    origen = Path(origen)
    destino = Path(destino)
    try:
        grabacion = json.loads(origen.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GrabacionInvalida(
            f"no se pudo leer la grabación ({type(exc).__name__})"
        ) from exc
    except ValueError as exc:
        raise GrabacionInvalida("la grabación no es JSON válido") from exc

    datos = construir_grabadas(grabacion, recorded_at=recorded_at)
    validadas = responses.validar_grabadas(datos, destino.name)

    # Se escribe en un archivo vecino y recién después se reemplaza el destino:
    # el destino habitual es el archivo versionado, y una escritura que falla
    # por la mitad no puede dejarlo truncado.
    contenido = json.dumps(datos, ensure_ascii=False, indent=2) + "\n"
    temporal = destino.with_name(destino.name + ".tmp")
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal.write_text(contenido, encoding="utf-8")
        os.replace(temporal, destino)
    except OSError as exc:
        try:
            temporal.unlink(missing_ok=True)
        except OSError:
            # Sin poder borrar el temporal no hay más que hacer: lo que importa
            # es informar el fallo original, que es el que sigue abajo.
            pass
        raise DestinoNoEscribible(
            f"no se pudo escribir el destino ({type(exc).__name__})"
        ) from exc
    return {
        "tasks": len(validadas),
        "entries": sum(len(entradas) for entradas in validadas.values()),
        "truncated": sum(1 for e in grabacion["entries"] if e.get("truncated") is True),
    }
