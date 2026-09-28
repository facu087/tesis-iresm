"""
Esquemas Pydantic de la revisión admin de cuentas pendientes (Sprint 4).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CuentaPendienteOut(BaseModel):
    """Una fila del listado de `GET /api/admin/pendientes`."""

    id: int
    nombre: str | None = None
    apellido: str | None = None
    dni: str | None = None
    matricula: str | None = None
    jurisdiccion: str | None = None
    profesion: str | None = None
    email: str
    creada_en: datetime
    enlace_refeps: str
    enlace_provincial: str | None = None


class AprobarCuentaRequest(BaseModel):
    """`revision-admin-matriculas` — Requirement: Aprobación de una cuenta pendiente."""

    fuente_consultada: str = Field(min_length=1)
    nota: str = ""


class RechazarCuentaRequest(BaseModel):
    """`revision-admin-matriculas` — Requirement: Rechazo con motivo obligatorio."""

    motivo: str = Field(min_length=1)
    fuente_consultada: str = ""
