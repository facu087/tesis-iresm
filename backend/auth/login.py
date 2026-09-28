"""
Autenticación por email y contraseña — login y límite de intentos.

`autenticar()` devuelve `None` para email inexistente, contraseña incorrecta
y cuenta bloqueada por igual: ese único resultado es lo que le permite al
endpoint devolver siempre el mismo mensaje genérico
(`autenticacion-medicos` — Requirement: Sin enumeración de usuarios). El
contador y el bloqueo se persisten en la propia `CuentaMedico`, no en el
rate limiter de APIs externas (`backend/external/rate_limiter.py`): ese
resuelve reintentos contra terceros, este resuelve fuerza bruta sobre login
(design.md — D3, nota sobre rate limiting).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..models.cuenta import CuentaMedico
from .security import verify_password

MAX_INTENTOS_FALLIDOS = 5
BLOQUEO_MINUTOS = 15


def autenticar(session: Session, email: str, password: str) -> CuentaMedico | None:
    """
    Autentica sin importar el estado de la cuenta de médico
    (`autenticacion-medicos` — Requirement: Login con email institucional y
    contraseña): un médico `pendiente` puede loguearse para ver su estado.
    """
    cuenta = session.exec(select(CuentaMedico).where(CuentaMedico.email == email)).first()
    ahora = datetime.now(timezone.utc)

    if cuenta is None:
        return None

    if cuenta.bloqueada_hasta is not None and cuenta.bloqueada_hasta > ahora:
        return None

    if not verify_password(password, cuenta.password_hash):
        cuenta.intentos_fallidos += 1
        if cuenta.intentos_fallidos >= MAX_INTENTOS_FALLIDOS:
            cuenta.bloqueada_hasta = ahora + timedelta(minutes=BLOQUEO_MINUTOS)
        session.add(cuenta)
        session.commit()
        return None

    if cuenta.intentos_fallidos or cuenta.bloqueada_hasta:
        cuenta.intentos_fallidos = 0
        cuenta.bloqueada_hasta = None
        session.add(cuenta)
        session.commit()
    return cuenta
