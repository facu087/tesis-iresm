"""
Router FastAPI — registro, login, logout y estado de cuenta (Sprint 4).

Sin middleware global de autenticación (design.md — D4): cada endpoint
declara explícitamente qué exige. Registro y login quedan alcanzables sin
sesión a propósito.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from ..auth.deps import get_session_dep, requerir_sesion
from ..auth.sesiones import COOKIE_NAME
from ..auth.login import autenticar
from ..auth.origen import validar_origen
from ..auth.security import hash_password
from ..auth.sesiones import clear_session_cookie, crear_sesion, invalidar_sesion, set_session_cookie
from ..models.cuenta import CuentaMedico, EstadoCuenta, RolCuenta
from .schemas_cuentas import CuentaEstadoResponse, LoginRequest, RegistroMedicoRequest

router = APIRouter(prefix="/api", tags=["cuentas"])

_MENSAJE_LOGIN_INVALIDO = "Email o contraseña incorrectos."


def _verificar_unicidad(
    session: Session,
    payload: RegistroMedicoRequest,
    *,
    excluir_id: int | None = None,
) -> None:
    """
    `registro-medicos` — Requirement: Unicidad de identidad. `excluir_id` se
    usa en el reenvío tras un rechazo, para no chocar contra la propia fila.
    """
    dni = session.exec(select(CuentaMedico).where(CuentaMedico.dni == payload.dni)).first()
    if dni is not None and dni.id != excluir_id:
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese DNI.")

    email = session.exec(select(CuentaMedico).where(CuentaMedico.email == payload.email)).first()
    if email is not None and email.id != excluir_id:
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email.")

    matricula = session.exec(
        select(CuentaMedico).where(
            CuentaMedico.matricula == payload.matricula,
            CuentaMedico.jurisdiccion == payload.jurisdiccion,
        )
    ).first()
    if matricula is not None and matricula.id != excluir_id:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una cuenta con esa matrícula en esa jurisdicción.",
        )


@router.post(
    "/registro",
    status_code=201,
    response_model=CuentaEstadoResponse,
    dependencies=[Depends(validar_origen)],
)
def registrar(
    payload: RegistroMedicoRequest,
    session: Session = Depends(get_session_dep),
) -> CuentaEstadoResponse:
    """
    Alta de médico. La cuenta nace `pendiente`
    (`registro-medicos` — Requirement: Estado inicial de la cuenta).
    """
    if not payload.acepta_tratamiento_datos:
        raise HTTPException(
            status_code=422,
            detail="Debe aceptar el tratamiento de datos personales (Ley 25.326).",
        )

    _verificar_unicidad(session, payload)

    cuenta = CuentaMedico(
        nombre=payload.nombre,
        apellido=payload.apellido,
        dni=payload.dni,
        matricula=payload.matricula,
        jurisdiccion=payload.jurisdiccion,
        profesion=payload.profesion,
        email=payload.email,
        password_hash=hash_password(payload.password),
        rol=RolCuenta.MEDICO,
        estado=EstadoCuenta.PENDIENTE,
        consentimiento_en=datetime.now(timezone.utc),
    )
    session.add(cuenta)
    session.commit()
    session.refresh(cuenta)
    return CuentaEstadoResponse(**cuenta.model_dump())


@router.put(
    "/registro",
    response_model=CuentaEstadoResponse,
    dependencies=[Depends(validar_origen)],
)
def reenviar_registro(
    payload: RegistroMedicoRequest,
    cuenta: CuentaMedico = Depends(requerir_sesion),
    session: Session = Depends(get_session_dep),
) -> CuentaEstadoResponse:
    """
    Corrección y reenvío tras un rechazo
    (`registro-medicos` — Requirement: Corrección y reenvío tras un rechazo).
    """
    if cuenta.rol != RolCuenta.MEDICO or cuenta.estado != EstadoCuenta.RECHAZADO:
        raise HTTPException(
            status_code=409,
            detail="Solo una cuenta de médico en estado 'rechazado' puede reenviar el registro.",
        )
    if not payload.acepta_tratamiento_datos:
        raise HTTPException(
            status_code=422,
            detail="Debe aceptar el tratamiento de datos personales (Ley 25.326).",
        )

    _verificar_unicidad(session, payload, excluir_id=cuenta.id)

    cuenta.nombre = payload.nombre
    cuenta.apellido = payload.apellido
    cuenta.dni = payload.dni
    cuenta.matricula = payload.matricula
    cuenta.jurisdiccion = payload.jurisdiccion
    cuenta.profesion = payload.profesion
    cuenta.email = payload.email
    cuenta.password_hash = hash_password(payload.password)
    cuenta.estado = EstadoCuenta.PENDIENTE
    cuenta.motivo_rechazo = None
    session.add(cuenta)
    session.commit()
    session.refresh(cuenta)
    return CuentaEstadoResponse(**cuenta.model_dump())


@router.post("/login", dependencies=[Depends(validar_origen)])
def login(
    payload: LoginRequest,
    response: Response,
    session: Session = Depends(get_session_dep),
) -> CuentaEstadoResponse:
    cuenta = autenticar(session, payload.email, payload.password)
    if cuenta is None:
        raise HTTPException(status_code=401, detail=_MENSAJE_LOGIN_INVALIDO)

    valor_cookie = crear_sesion(session, cuenta)
    set_session_cookie(response, valor_cookie)
    # `crear_sesion()` hace su propio commit, que expira los atributos ya
    # cargados de `cuenta` en esta sesión; refrescar antes de serializar.
    session.refresh(cuenta)
    return CuentaEstadoResponse(**cuenta.model_dump())


@router.post("/logout", dependencies=[Depends(validar_origen)])
def logout(
    request: Request,
    response: Response,
    _cuenta: CuentaMedico = Depends(requerir_sesion),
    session: Session = Depends(get_session_dep),
) -> dict[str, bool]:
    """
    `autenticacion-medicos` — Requirement: Sesión tras login exitoso,
    Scenario: Cierre de sesión. Borra la fila en `Sesion` (revocación real,
    no solo la cookie) y limpia la cookie del navegador.
    """
    token = request.cookies.get(COOKIE_NAME)
    if token:
        invalidar_sesion(session, token)
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/cuenta", response_model=CuentaEstadoResponse)
def consultar_cuenta(cuenta: CuentaMedico = Depends(requerir_sesion)) -> CuentaEstadoResponse:
    """`registro-medicos` — Requirement: Consulta del estado de la cuenta."""
    return CuentaEstadoResponse(**cuenta.model_dump())
