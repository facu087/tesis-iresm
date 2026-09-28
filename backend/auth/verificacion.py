"""
Punto de extensión para una verificación automática de matrícula futura
(design.md — D6). Sin implementación concreta en este cambio: la revisión
manual del administrador (`revision-admin-matriculas`) es el único
"provider" activo, y el flujo de aprobación no depende de que exista uno
automático — solo lo consultaría si algún día está configurado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class LicenseCheckResult:
    """Resultado de una consulta automática a un padrón de matrículas."""

    coincide: bool
    detalle: str = ""


class LicenseVerificationProvider(Protocol):
    """
    Interfaz angosta para un futuro chequeo automático contra un padrón
    oficial (p. ej. SISA/REFEPS `WS020`, si algún día se aprueba el
    Formulario A1 — ver `proposal.md`, Why). Ninguna implementación concreta
    existe todavía.
    """

    def check(self, matricula: str, jurisdiccion: str) -> LicenseCheckResult | None:
        """
        Consulta el padrón. Devuelve `None` ante cualquier resultado no
        concluyente (falla la API, no hay provider configurado, etc.) — nunca
        decide por sí sola: la aprobación humana sigue siendo la única vía en
        este cambio.
        """
        ...
