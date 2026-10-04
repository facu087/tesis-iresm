"""
Modelo de sesión de servidor — capa de persistencia (Sprint 4).

`Sesion` es la fuente de verdad de si una sesión es válida (design.md — D3):
el id opaco viaja firmado en la cookie, pero lo que decide autenticación es
que exista una fila no expirada con ese id, no la firma. Cerrar sesión borra
la fila; eso alcanza para revocación inmediata sin mantener una denylist.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Sesion(SQLModel, table=True):
    """Sesión de servidor asociada a una `CuentaMedico`."""

    __tablename__ = "sesion"

    id: str = Field(primary_key=True)  # token opaco aleatorio
    cuenta_id: int = Field(foreign_key="cuenta_medico.id", index=True)
    creada_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expira_en: datetime
