"""
Dependencias FastAPI de sesión y autorización (design.md — D4).

Dependencias por endpoint, no middleware global: el registro y el login
deben quedar alcanzables sin sesión. `requerir_sesion` distingue "no hay
sesión" (401) de "hay sesión pero no alcanza el rol/estado exigido" (403).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from ..db import get_session
from ..models.cuenta import CuentaMedico, EstadoCuenta, RolCuenta
from .sesiones import COOKIE_NAME, resolver_sesion

# Alias con nombre estable para que los tests puedan overridear la sesión de
# base de datos sin depender de que `backend.db.get_session` no cambie de
# módulo de origen.
get_session_dep = get_session


def get_cuenta_actual(
    request: Request,
    session: Session = Depends(get_session_dep),
) -> CuentaMedico | None:
    """Cuenta asociada a la cookie de sesión, o `None` si no hay sesión válida."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return resolver_sesion(session, token)


def requerir_sesion(
    cuenta: CuentaMedico | None = Depends(get_cuenta_actual),
) -> CuentaMedico:
    """Exige una sesión autenticada válida. 401 si no hay ninguna."""
    if cuenta is None:
        raise HTTPException(status_code=401, detail="Sesión requerida.")
    return cuenta


def requerir_admin(
    cuenta: CuentaMedico = Depends(requerir_sesion),
) -> CuentaMedico:
    """Exige rol `admin` (`revision-admin-matriculas` — Acceso restringido a administradores)."""
    if cuenta.rol != RolCuenta.ADMIN:
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores.")
    return cuenta


def requerir_medico_verificado(
    cuenta: CuentaMedico = Depends(requerir_sesion),
) -> CuentaMedico:
    """
    Exige rol `medico` en estado `verificado`
    (`proteccion-analisis-clinico` — Solo médicos verificados pueden analizar).

    Rechaza también a una cuenta `admin` sin cuenta de médico verificada:
    esta tabla es única por cuenta, así que un admin nunca tiene además una
    cuenta médico separada en este diseño.
    """
    if cuenta.rol != RolCuenta.MEDICO or cuenta.estado != EstadoCuenta.VERIFICADO:
        raise HTTPException(
            status_code=403, detail="Requiere una cuenta de médico verificada."
        )
    return cuenta
