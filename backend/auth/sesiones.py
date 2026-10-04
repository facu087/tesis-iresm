"""
Sesión de servidor — creación, resolución e invalidación (design.md — D3).

La fila en `Sesion` es la fuente de verdad de si una sesión es válida, no la
firma de la cookie: `SECRET_KEY` firma el token opaco (HMAC-SHA256, sin
sumar una dependencia nueva) para que no sea manipulable, pero revocar acceso
(logout, o que un admin corte una cuenta) alcanza con borrar la fila — sin
mantener una denylist aparte, a diferencia de un JWT autocontenido.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Response
from sqlmodel import Session

from ..models.cuenta import CuentaMedico
from ..models.sesion import Sesion

COOKIE_NAME = "nexus_sesion"

_SECRET_KEY_ENV = "SECRET_KEY"
_SESSION_TTL_ENV = "SESSION_TTL_MINUTES"
_DEFAULT_TTL_MINUTES = 60


class SecretKeyNoConfigurada(RuntimeError):
    """`SECRET_KEY` no está definida en el entorno — no se puede firmar la sesión."""


def _secret_key() -> bytes:
    clave = os.getenv(_SECRET_KEY_ENV, "")
    if not clave:
        raise SecretKeyNoConfigurada(
            "SECRET_KEY no está configurada. Definila en .env antes de levantar el backend."
        )
    return clave.encode("utf-8")


def _firmar(token: str) -> str:
    firma = hmac.new(_secret_key(), token.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{token}.{firma}"


def _desfirmar(valor_cookie: str) -> str | None:
    try:
        token, firma = valor_cookie.rsplit(".", 1)
    except ValueError:
        return None
    esperada = hmac.new(_secret_key(), token.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(firma, esperada):
        return None
    return token


def _ttl_minutos() -> int:
    try:
        return int(os.getenv(_SESSION_TTL_ENV, str(_DEFAULT_TTL_MINUTES)))
    except ValueError:
        return _DEFAULT_TTL_MINUTES


def crear_sesion(session: Session, cuenta: CuentaMedico, *, ahora: datetime | None = None) -> str:
    """
    Crea una fila en `Sesion` para `cuenta` y devuelve el valor firmado listo
    para la cookie. `ahora` es un punto de extensión para tests: permite
    crear una sesión ya vencida sin depender de `time.sleep`.
    """
    momento = ahora or datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    fila = Sesion(
        id=token,
        cuenta_id=cuenta.id,
        creada_en=momento,
        expira_en=momento + timedelta(minutes=_ttl_minutos()),
    )
    session.add(fila)
    session.commit()
    return _firmar(token)


def resolver_sesion(session: Session, valor_cookie: str) -> CuentaMedico | None:
    """
    Devuelve la cuenta asociada a `valor_cookie` si la firma es válida y la
    sesión no expiró; `None` en cualquier otro caso (firma inválida, sesión
    inexistente o vencida). Una sesión vencida se trata como inexistente.
    """
    token = _desfirmar(valor_cookie)
    if token is None:
        return None

    fila = session.get(Sesion, token)
    if fila is None:
        return None

    if fila.expira_en <= datetime.now(timezone.utc):
        return None

    return session.get(CuentaMedico, fila.cuenta_id)


def invalidar_sesion(session: Session, valor_cookie: str) -> None:
    """Borra la fila de `Sesion` asociada a `valor_cookie`, si existe."""
    token = _desfirmar(valor_cookie)
    if token is None:
        return
    fila = session.get(Sesion, token)
    if fila is not None:
        session.delete(fila)
        session.commit()


def set_session_cookie(response: Response, valor_cookie: str) -> None:
    """
    Fija la cookie de sesión: `httpOnly`, `SameSite=Lax`, `Secure` cuando
    `ENVIRONMENT=production` (design.md — D3).
    """
    es_produccion = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(
        key=COOKIE_NAME,
        value=valor_cookie,
        max_age=_ttl_minutos() * 60,
        httponly=True,
        samesite="lax",
        secure=es_produccion,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Borra la cookie de sesión del navegador (logout)."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
