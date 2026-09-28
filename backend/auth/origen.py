"""
Validación de origen — mitigación CSRF (design.md — D3, corregido).

`multipart/form-data` es una solicitud "simple" para CORS y no dispara
preflight, así que CORS nunca protegió `POST /api/analyze`. Esta dependencia
valida `Origin` (con `Referer` como respaldo) contra la misma lista blanca
que ya usa `CORSMiddleware` (`ALLOWED_ORIGINS`), sin importar el tipo de
contenido. *Fail-closed*: si ninguno de los dos encabezados está presente,
rechaza igual que si no coincidiera.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

_ALLOWED_ORIGINS_ENV = "ALLOWED_ORIGINS"
_DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000"


def _allowed_origins() -> list[str]:
    valor = os.getenv(_ALLOWED_ORIGINS_ENV, _DEFAULT_ALLOWED_ORIGINS)
    return [o.strip() for o in valor.split(",") if o.strip()]


def _origen_efectivo(request: Request) -> str | None:
    """`Origin` si está presente; si no, el esquema+host del `Referer`."""
    origin = request.headers.get("origin")
    if origin:
        return origin

    referer = request.headers.get("referer")
    if referer:
        partes = urlsplit(referer)
        if partes.scheme and partes.netloc:
            return f"{partes.scheme}://{partes.netloc}"

    return None


def validar_origen(request: Request) -> None:
    """
    Dependencia FastAPI para todo endpoint que cambia estado.

    Rechaza con 403 si el origen efectivo de la solicitud (`Origin`, o
    `Referer` como respaldo) no pertenece a `ALLOWED_ORIGINS`.
    """
    origen = _origen_efectivo(request)
    if origen is None or origen not in _allowed_origins():
        raise HTTPException(status_code=403, detail="Origen no permitido.")
