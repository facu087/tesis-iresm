"""
Router FastAPI — revisión admin de cuentas pendientes (Sprint 4, sección 5).

Todas las rutas exigen rol `admin` (`requerir_admin`); las que cambian
estado exigen además `Origin`/`Referer` permitido (design.md — D3).
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..auth.deps import get_session_dep, requerir_admin
from ..auth.origen import validar_origen
from ..models.auditoria import DecisionAuditoria, DecisionTipo
from ..models.cuenta import CuentaMedico, EstadoCuenta
from .schemas_admin import AprobarCuentaRequest, CuentaPendienteOut, RechazarCuentaRequest
from .schemas_cuentas import CuentaEstadoResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])

# `revision-admin-matriculas` — Requirement: Enlaces a los buscadores
# públicos de matrícula. El Buscador Nacional REFEPS no es configurable.
_ENLACE_REFEPS = "https://www.argentina.gob.ar/salud/buscador-nacional-de-profesionales-de-la-salud"
_PROVINCIAL_ENV = "PROVINCIAL_LICENSE_SEARCH_URL"


def _enlace_provincial() -> str | None:
    valor = os.getenv(_PROVINCIAL_ENV, "").strip()
    return valor or None


@router.get("/pendientes", response_model=list[CuentaPendienteOut])
def listar_pendientes(
    admin: CuentaMedico = Depends(requerir_admin),
    session: Session = Depends(get_session_dep),
) -> list[CuentaPendienteOut]:
    """`revision-admin-matriculas` — Requirement: Listado de cuentas pendientes."""
    pendientes = session.exec(
        select(CuentaMedico).where(CuentaMedico.estado == EstadoCuenta.PENDIENTE)
    ).all()
    enlace_provincial = _enlace_provincial()
    return [
        CuentaPendienteOut(
            id=c.id,
            nombre=c.nombre,
            apellido=c.apellido,
            dni=c.dni,
            matricula=c.matricula,
            jurisdiccion=c.jurisdiccion,
            profesion=c.profesion,
            email=c.email,
            creada_en=c.creada_en,
            enlace_refeps=_ENLACE_REFEPS,
            enlace_provincial=enlace_provincial,
        )
        for c in pendientes
    ]


def _obtener_pendiente(session: Session, cuenta_id: int) -> CuentaMedico:
    cuenta = session.get(CuentaMedico, cuenta_id)
    if cuenta is None or cuenta.estado != EstadoCuenta.PENDIENTE:
        raise HTTPException(status_code=404, detail="Cuenta pendiente no encontrada.")
    return cuenta


@router.post(
    "/cuentas/{cuenta_id}/aprobar",
    response_model=CuentaEstadoResponse,
    dependencies=[Depends(validar_origen)],
)
def aprobar_cuenta(
    cuenta_id: int,
    payload: AprobarCuentaRequest,
    admin: CuentaMedico = Depends(requerir_admin),
    session: Session = Depends(get_session_dep),
) -> CuentaEstadoResponse:
    """`revision-admin-matriculas` — Requirement: Aprobación de una cuenta pendiente."""
    if not payload.fuente_consultada.strip():
        raise HTTPException(status_code=422, detail="Debe indicar la fuente consultada.")

    cuenta = _obtener_pendiente(session, cuenta_id)
    cuenta.estado = EstadoCuenta.VERIFICADO
    cuenta.motivo_rechazo = None
    session.add(cuenta)
    session.add(
        DecisionAuditoria(
            admin_id=admin.id,
            cuenta_id=cuenta.id,
            decision=DecisionTipo.APROBADO,
            motivo=payload.nota,
            fuente_consultada=payload.fuente_consultada,
        )
    )
    session.commit()
    session.refresh(cuenta)
    return CuentaEstadoResponse(**cuenta.model_dump())


@router.post(
    "/cuentas/{cuenta_id}/rechazar",
    response_model=CuentaEstadoResponse,
    dependencies=[Depends(validar_origen)],
)
def rechazar_cuenta(
    cuenta_id: int,
    payload: RechazarCuentaRequest,
    admin: CuentaMedico = Depends(requerir_admin),
    session: Session = Depends(get_session_dep),
) -> CuentaEstadoResponse:
    """`revision-admin-matriculas` — Requirement: Rechazo con motivo obligatorio."""
    if not payload.motivo.strip():
        raise HTTPException(status_code=422, detail="Debe indicar el motivo del rechazo.")

    cuenta = _obtener_pendiente(session, cuenta_id)
    cuenta.estado = EstadoCuenta.RECHAZADO
    cuenta.motivo_rechazo = payload.motivo
    session.add(cuenta)
    session.add(
        DecisionAuditoria(
            admin_id=admin.id,
            cuenta_id=cuenta.id,
            decision=DecisionTipo.RECHAZADO,
            motivo=payload.motivo,
            fuente_consultada=payload.fuente_consultada,
        )
    )
    session.commit()
    session.refresh(cuenta)
    return CuentaEstadoResponse(**cuenta.model_dump())
