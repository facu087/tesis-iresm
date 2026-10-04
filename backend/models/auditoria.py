"""
Modelo de auditoría de decisiones admin — capa de persistencia (Sprint 4).

`DecisionAuditoria` deja constancia inmutable de cada aprobación o rechazo de
una cuenta de médico (`revision-admin-matriculas` — Requirement: Auditoría de
cada decisión). No hay ruta de edición ni borrado sobre esta tabla: se
inserta una fila por decisión y no se toca más.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class DecisionTipo(str, Enum):
    """Qué decidió el administrador sobre una cuenta pendiente."""

    APROBADO = "aprobado"
    RECHAZADO = "rechazado"


class DecisionAuditoria(SQLModel, table=True):
    """
    Registro inmutable de una aprobación o rechazo.

    `motivo` cumple doble función según `decision`: es el motivo obligatorio
    de un rechazo, o la nota opcional de una aprobación — el mismo campo
    porque ambos son texto libre del administrador sobre la misma decisión.
    """

    __tablename__ = "decision_auditoria"

    id: int | None = Field(default=None, primary_key=True)
    admin_id: int = Field(foreign_key="cuenta_medico.id", index=True)
    cuenta_id: int = Field(foreign_key="cuenta_medico.id", index=True)
    decidida_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    decision: DecisionTipo
    motivo: str = Field(default="")
    fuente_consultada: str = Field(default="")
