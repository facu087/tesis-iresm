"""
Modelo de cuenta de médico/administrador — capa de persistencia (Sprint 4).

`CuentaMedico` es la única tabla de cuentas del sistema: un médico que se
registra y un administrador dado de alta por el CLI de bootstrap son la misma
tabla, distinguidos por `rol`. Los campos de identidad y matrícula
(`nombre`, `apellido`, `dni`, `matricula`, `jurisdiccion`) son opcionales a
nivel de esquema porque una cuenta `admin` no los declara — la obligatoriedad
para el registro de médicos (`registro-medicos` — Requirement: Datos
obligatorios del registro) se exige en el schema de la request
(`backend/api/schemas_cuentas.py`), no en esta tabla.

Nunca persistir texto clínico ni reportes en este módulo (`registro-medicos`
— Requirement: Sin datos clínicos en el registro de cuentas).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel, UniqueConstraint


class RolCuenta(str, Enum):
    """Rol de una cuenta. Toda cuenta tiene exactamente uno."""

    MEDICO = "medico"
    ADMIN = "admin"


class EstadoCuenta(str, Enum):
    """Estado del ciclo de vida de una cuenta de médico."""

    PENDIENTE = "pendiente"
    RECHAZADO = "rechazado"
    VERIFICADO = "verificado"


class CuentaMedico(SQLModel, table=True):
    """
    Cuenta de médico o administrador.

    La combinación (`matricula`, `jurisdiccion`) es única a nivel de base de
    datos: dos cuentas no pueden declarar la misma matrícula en la misma
    jurisdicción. `dni` y `email` también son únicos. Ninguna de las tres
    restricciones se dispara entre cuentas `admin`, que dejan esos campos en
    `None` (NULL no es igual a NULL en SQLite).
    """

    __tablename__ = "cuenta_medico"
    __table_args__ = (
        UniqueConstraint("matricula", "jurisdiccion", name="uq_matricula_jurisdiccion"),
    )

    id: int | None = Field(default=None, primary_key=True)

    # Identidad y matrícula — obligatorios para un médico, ausentes en un admin.
    nombre: str | None = None
    apellido: str | None = None
    dni: str | None = Field(default=None, unique=True, index=True)
    matricula: str | None = None
    jurisdiccion: str | None = None
    profesion: str | None = None  # Especialidad — siempre opcional (incluso para médicos)

    # Credenciales y acceso
    email: str = Field(unique=True, index=True)
    password_hash: str

    rol: RolCuenta = Field(default=RolCuenta.MEDICO)
    estado: EstadoCuenta = Field(default=EstadoCuenta.PENDIENTE)
    motivo_rechazo: str | None = None

    # Consentimiento explícito Ley 25.326 (registro-medicos — Requirement:
    # Consentimiento explícito). None solo puede darse en una cuenta admin,
    # que no pasa por el formulario de registro.
    consentimiento_en: datetime | None = None

    # Reservado para verificación de email por correo — diferido a un cambio
    # posterior (design.md — Non-Goals). Ningún flujo lo pone en True todavía.
    email_verificado: bool = Field(default=False)

    # Límite de intentos de login fallidos (autenticacion-medicos —
    # Requirement: Límite de intentos de login). Persistido en la cuenta, no
    # en el rate limiter de APIs externas (backend/external/rate_limiter.py):
    # resuelve un problema distinto.
    intentos_fallidos: int = Field(default=0)
    bloqueada_hasta: datetime | None = None

    creada_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
