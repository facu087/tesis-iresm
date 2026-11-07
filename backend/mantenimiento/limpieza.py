"""
Limpieza automática de datos vencidos (Sprint 5 — tarjeta #56).

## Qué limpia, y por qué no limpia archivos

La tarjeta pedía un job que borrara "archivos de sesión expirados". Al revisar
el pipeline se verificó que **esos archivos no existen**:

- `POST /api/analyze` recibe el PDF con `UploadFile.read()` y le pasa los
  bytes a `ingestion.extractor.extract()`, que trabaja en memoria
  (`io.BytesIO` para pdfplumber, `pypdfium2.PdfDocument(file_bytes)` para el
  OCR). El texto clínico vive en variables locales y se va con la respuesta.
- `POST /api/report/pdf` arma el PDF en memoria y lo devuelve en el cuerpo.
- No hay `tempfile`, ni `NamedTemporaryFile`, ni directorio de subidas, ni
  ninguna escritura del texto clínico a disco en todo el backend.
- Las entradas `uploads/` y `temp/` del `.gitignore` son de un plan que nunca
  se implementó: ningún módulo las referencia.

Es decir: el principio de la tesis "no se almacenan datos clínicos
identificables más allá de la sesión activa" se cumple **por construcción**
del lado de los archivos, y no hace falta un job que borre nada. Inventarlo
sería código que no limpia nada. `tests/test_limpieza_temporales.py` fija esa
propiedad como invariante, para que una regresión futura (alguien que guarde
el PDF subido en disco) rompa un test en vez de pasar inadvertida.

Lo que **sí** se acumulaba sin borrarse nunca son las filas de la tabla
`sesion`: `auth.sesiones.resolver_sesion()` trata una sesión vencida como
inexistente, pero la fila queda en `data/nexus.db` para siempre. Eso es dato
personal —qué cuenta inició sesión y cuándo— sobreviviendo indefinidamente a
la sesión que lo justificaba, y acumula un historial de ingresos de cada
médico que nadie pidió conservar. Este módulo las borra.

## Cómo se dispara

`backend.main` arranca `bucle_de_limpieza()` como tarea de fondo en el
`lifespan` de FastAPI: una pasada al levantar el backend y otra cada
`SESSION_CLEANUP_INTERVAL_MINUTES` minutos (default 15; `0` apaga la tarea).

Se eligió la tarea de fondo en lugar de la limpieza oportunista al iniciar
cada análisis por dos razones:

1. El borrado tiene que ocurrir en un plazo acotado que **no dependa del
   tráfico**. Con limpieza oportunista, un fin de semana sin análisis deja
   intacto el historial de ingresos en la base: la garantía de privacidad
   quedaría atada a que alguien suba un documento, que es justo al revés.
2. `POST /api/analyze` es el camino que menos conviene cargar con trabajo
   ajeno: ya tarda cientos de segundos y es el único que no debe fallar.

El intervalo se lee del entorno en cada llamada, no al importar el módulo,
con el mismo criterio que `db.resolve_db_path()`: así los tests lo controlan
con `monkeypatch` sin depender del orden de los imports.

## Reglas que respeta

- **Nunca rompe el arranque ni un análisis en curso.** Cada pasada atrapa su
  excepción, la informa por stderr y devuelve un `ResultadoLimpieza` con
  `ok=False`. El `lifespan` tolera que la tarea no arranque. Nunca
  `except: pass`: cada captura nombra la excepción que espera y deja registro.
- **No corta ninguna sesión viva.** Solo borra filas con `expira_en <= ahora`,
  que `resolver_sesion()` ya rechazaba antes de este cambio: borrarlas no
  cambia el comportamiento observable de ninguna solicitud.
- **Los logs llevan conteos y duraciones, nada más.** Nunca un email, un id de
  cuenta, un token de sesión, un nombre de archivo ni texto clínico. Ante un
  fallo se informa el **tipo** de la excepción, nunca su mensaje, que puede
  arrastrar valores de la fila.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy import Engine, delete
from sqlmodel import Session

from .. import db as db_module
from ..models.sesion import Sesion

_INTERVALO_ENV = "SESSION_CLEANUP_INTERVAL_MINUTES"
_INTERVALO_POR_DEFECTO_MINUTOS = 15


class ResultadoLimpieza(BaseModel):
    """
    Resultado de una pasada de limpieza.

    Solo conteos y tiempos: nunca un identificador de cuenta, un token ni el
    mensaje de una excepción. `fallo` guarda el **nombre de la clase** de la
    excepción (p. ej. `"OperationalError"`), que alcanza para diagnosticar sin
    filtrar datos de la fila.
    """

    sesiones_expiradas_borradas: int = Field(default=0, ge=0)
    ejecutada_en: datetime
    duracion_segundos: float = Field(default=0.0, ge=0.0)
    ok: bool = True
    fallo: str | None = None


def intervalo_minutos() -> int:
    """
    Minutos entre pasadas, leídos de `SESSION_CLEANUP_INTERVAL_MINUTES`.

    Devuelve el default (15) si la variable no está definida o está vacía, y
    también si tiene un valor que no es un entero —en ese caso avisa por
    stderr en lugar de fallar: una variable mal tipeada no puede impedir que
    el backend arranque, pero tampoco puede apagar la limpieza en silencio—.
    `0` o un valor negativo apagan la tarea de fondo deliberadamente.
    """
    crudo = os.getenv(_INTERVALO_ENV)
    if crudo is None or not crudo.strip():
        return _INTERVALO_POR_DEFECTO_MINUTOS
    try:
        valor = int(crudo.strip())
    except ValueError:
        print(
            f"[NEXUS] limpieza: {_INTERVALO_ENV} no es un número entero; "
            f"se usa el default de {_INTERVALO_POR_DEFECTO_MINUTOS} minutos.",
            file=sys.stderr,
        )
        return _INTERVALO_POR_DEFECTO_MINUTOS
    return max(valor, 0)


def purgar_sesiones_expiradas(
    session: Session, *, ahora: datetime | None = None
) -> int:
    """
    Borra las filas de `Sesion` con `expira_en <= ahora` y devuelve cuántas.

    `ahora` es el punto de extensión para los tests, con el mismo criterio que
    `auth.sesiones.crear_sesion()`: permite fijar el reloj y probar el borde
    sin `sleep` real. El comparador es `<=`, el mismo que usa
    `resolver_sesion()` para rechazar una sesión: una fila que vence
    exactamente ahora ya era inservible, así que se borra.
    """
    momento = ahora or datetime.now(timezone.utc)
    resultado = session.execute(delete(Sesion).where(Sesion.expira_en <= momento))
    borradas = resultado.rowcount or 0
    session.commit()
    return borradas


def ejecutar_limpieza(
    *, engine: Engine | None = None, ahora: datetime | None = None
) -> ResultadoLimpieza:
    """
    Corre una pasada completa de limpieza y devuelve su resultado.

    **Nunca levanta una excepción**: un fallo de la limpieza (base bloqueada,
    disco lleno, esquema inexistente) no puede tumbar el arranque del backend
    ni cortar un análisis en curso. Ante el fallo se informa el tipo de
    excepción por stderr y se devuelve un resultado con `ok=False` y
    `sesiones_expiradas_borradas=0` — el fallback explícito: no se borró nada
    y la próxima pasada lo vuelve a intentar.

    El engine se resuelve en cada llamada desde `backend.db` (no se captura al
    importar) para que los tests puedan reemplazarlo con `set_engine()`.
    """
    inicio = time.perf_counter()
    momento = ahora or datetime.now(timezone.utc)
    destino = engine if engine is not None else db_module.engine

    try:
        with Session(destino) as session:
            borradas = purgar_sesiones_expiradas(session, ahora=momento)
    except Exception as exc:
        print(
            f"[NEXUS] limpieza: la pasada falló ({type(exc).__name__}). "
            "No se borró nada; el backend sigue y se reintenta en la próxima pasada.",
            file=sys.stderr,
        )
        return ResultadoLimpieza(
            ejecutada_en=momento,
            duracion_segundos=time.perf_counter() - inicio,
            ok=False,
            fallo=type(exc).__name__,
        )

    duracion = time.perf_counter() - inicio
    print(
        f"[NEXUS] limpieza: {borradas} sesiones expiradas borradas "
        f"en {duracion:.3f}s.",
        file=sys.stderr,
    )
    return ResultadoLimpieza(
        sesiones_expiradas_borradas=borradas,
        ejecutada_en=momento,
        duracion_segundos=duracion,
    )


async def bucle_de_limpieza(
    *,
    intervalo_segundos: float,
    engine: Engine | None = None,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """
    Corre una pasada al arrancar y otra cada `intervalo_segundos`, hasta que se
    cancele la tarea.

    La primera pasada va antes del primer `dormir` a propósito: si el backend
    estuvo caído más que el TTL, al volver hay sesiones vencidas que conviene
    borrar ya, no dentro de un intervalo.

    `dormir` se inyecta para que los tests controlen el reloj sin `sleep` real:
    el test pasa una función que cuenta las pasadas y después levanta
    `asyncio.CancelledError`, que es exactamente la salida real cuando se
    apaga el backend. `ejecutar_limpieza()` no levanta, así que el bucle no
    puede morir por un fallo de una pasada.
    """
    try:
        while True:
            ejecutar_limpieza(engine=engine)
            await dormir(intervalo_segundos)
    except asyncio.CancelledError:
        # Salida esperada: el `lifespan` cancela la tarea al apagar el backend.
        # Se relanza porque cancelar significa cancelar — tragarla dejaría a
        # asyncio creyendo que la tarea ignoró el pedido.
        print("[NEXUS] limpieza: tarea de fondo detenida.", file=sys.stderr)
        raise


def iniciar_tarea(*, engine: Engine | None = None) -> asyncio.Task[None] | None:
    """
    Crea la tarea de fondo de limpieza, o `None` si no corresponde.

    Devuelve `None` cuando el intervalo configurado es `0` (apagada a
    propósito) y también si la creación de la tarea falla: el arranque del
    backend nunca depende de que la limpieza arranque. En ese caso se avisa
    por stderr para que quede registro de que el backend está corriendo sin
    limpieza automática.
    """
    minutos = intervalo_minutos()
    if minutos <= 0:
        print(
            f"[NEXUS] limpieza: tarea de fondo apagada ({_INTERVALO_ENV}=0). "
            "Las sesiones vencidas no se van a borrar solas.",
            file=sys.stderr,
        )
        return None

    # Se chequea el loop *antes* de construir la corutina: si no hay loop,
    # `create_task()` levantaría dejando una corutina sin esperar (y su
    # RuntimeWarning). Así se sale limpio.
    try:
        asyncio.get_running_loop()
    except RuntimeError as exc:
        print(
            f"[NEXUS] limpieza: no se pudo arrancar la tarea de fondo "
            f"({type(exc).__name__}: no hay event loop corriendo). "
            "El backend sigue, sin limpieza automática.",
            file=sys.stderr,
        )
        return None

    tarea = asyncio.create_task(
        bucle_de_limpieza(intervalo_segundos=minutos * 60, engine=engine),
        name="nexus-limpieza",
    )

    print(
        f"[NEXUS] limpieza: tarea de fondo activa "
        f"(una pasada al arrancar y luego cada {minutos} min).",
        file=sys.stderr,
    )
    return tarea


async def detener_tarea(tarea: asyncio.Task[None] | None) -> None:
    """
    Cancela la tarea de fondo y espera su salida. Tolera `None`.

    La llama el `finally` del `lifespan`, así que tampoco puede levantar: si
    la tarea terminó con un error distinto de la cancelación, se informa el
    tipo y el apagado sigue.
    """
    if tarea is None:
        return

    tarea.cancel()
    try:
        # `CancelledError` es el resultado esperado: la cancelación la pedimos
        # nosotros dos líneas arriba. No se silencia otra cosa.
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
    except Exception as exc:
        print(
            f"[NEXUS] limpieza: la tarea de fondo terminó con un error "
            f"({type(exc).__name__}). El apagado continúa.",
            file=sys.stderr,
        )
