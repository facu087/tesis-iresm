"""
Esquemas Pydantic de request/response — registro, login y cuenta (Sprint 4).

Deliberadamente sin `EmailStr` de Pydantic: exigiría sumar `email-validator`
como dependencia nueva, y `design.md` solo justifica `sqlmodel` y
`argon2-cffi`. `_validar_email` alcanza para el nivel de validación que pide
`registro-medicos` (campo obligatorio, con forma de email).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from ..models.cuenta import EstadoCuenta, RolCuenta


def _validar_email(valor: str) -> str:
    valor = valor.strip()
    if "@" not in valor or valor.startswith("@") or valor.endswith("@") or " " in valor:
        raise ValueError("El email institucional no tiene un formato válido.")
    return valor


class RegistroMedicoRequest(BaseModel):
    """Alta o reenvío tras un rechazo (`registro-medicos`)."""

    nombre: str = Field(min_length=1)
    apellido: str = Field(min_length=1)
    dni: str = Field(min_length=1)
    matricula: str = Field(min_length=1)
    jurisdiccion: str = Field(min_length=1)
    profesion: str | None = None
    email: str
    password: str = Field(min_length=8)
    acepta_tratamiento_datos: bool

    _validar = field_validator("email")(_validar_email)


class LoginRequest(BaseModel):
    email: str
    password: str


class CuentaEstadoResponse(BaseModel):
    """Respuesta de `GET /api/cuenta` — el estado y los datos propios de la cuenta."""

    rol: RolCuenta
    estado: EstadoCuenta
    motivo_rechazo: str | None = None
    nombre: str | None = None
    apellido: str | None = None
    dni: str | None = None
    matricula: str | None = None
    jurisdiccion: str | None = None
    profesion: str | None = None
    email: str
