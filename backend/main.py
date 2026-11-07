"""
Punto de entrada de la aplicación FastAPI — NEXUS.

Arrancar con:
    uvicorn backend.main:app --reload
"""

import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .api.admin_router import router as admin_router
from .api.cuentas_router import router as cuentas_router
from .api.router import router
from .db import create_db_and_tables
from .mantenimiento import limpieza
from .mock.mode import ENV_VAR as _MOCK_ENV_VAR
from .mock.mode import is_mock_active
from .seguridad import (
    ENCABEZADOS_CORS,
    METODOS_CORS,
    EncabezadosDeSeguridad,
    es_produccion,
    hosts_permitidos,
    origenes_permitidos,
    urls_de_documentacion,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Crea el esquema de la base de cuentas si no existe (design.md — D1) y deja
    corriendo la limpieza periódica de sesiones vencidas (tarjeta #56).

    `iniciar_tarea()` devuelve `None` si la limpieza está apagada por
    configuración o si no pudo arrancar: el backend levanta igual. El
    `finally` cancela la tarea en el apagado, así que no queda un bucle
    huérfano entre reinicios del `--reload` de uvicorn.
    """
    create_db_and_tables()
    tarea_limpieza = limpieza.iniciar_tarea()
    try:
        yield
    finally:
        await limpieza.detener_tarea(tarea_limpieza)


if is_mock_active():
    # Spec `modo-mock-pipeline`, "Activación deliberada": el modo mock se
    # informa al arrancar, para que nadie lo active sin darse cuenta y
    # confunda un reporte grabado con uno producido de verdad.
    print(
        f"[NEXUS] Modo mock activo ({_MOCK_ENV_VAR}): el pipeline va a usar "
        "respuestas grabadas, sin llamar al proveedor del modelo.",
        file=sys.stderr,
    )

app = FastAPI(
    title="NEXUS — Sistema de Soporte Investigativo Clínico",
    description=(
        "Pipeline multi-agente para generación de hipótesis clínicas basadas en evidencia. "
        "**NEXUS no emite diagnósticos** — genera hipótesis de investigación "
        "para el médico responsable."
    ),
    version="0.3.0",
    lifespan=lifespan,
    # La documentación interactiva solo existe fuera de producción.
    **urls_de_documentacion(),
)

# Configuración insegura = el servidor no arranca (ver backend/seguridad.py).
# El orden importa: el último `add_middleware` es el más externo, y los
# encabezados de seguridad tienen que cubrir también las respuestas que
# generan el CORS (preflight) y la validación de host.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes_permitidos(),
    allow_credentials=True,
    # Solo lo que el frontend usa (frontend/src/lib/api.ts), no "*".
    allow_methods=METODOS_CORS,
    allow_headers=ENCABEZADOS_CORS,
)

_HOSTS = hosts_permitidos()
if _HOSTS is not None:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_HOSTS)
elif es_produccion():
    print(
        "[NEXUS] ALLOWED_HOSTS no está definida en producción: el servidor acepta "
        "cualquier encabezado Host. Definila con los dominios del despliegue.",
        file=sys.stderr,
    )

app.add_middleware(EncabezadosDeSeguridad, hsts=es_produccion())

app.include_router(cuentas_router)
app.include_router(admin_router)
app.include_router(router)


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    """Verificación de estado del servicio."""
    return {"status": "ok", "service": "NEXUS", "version": "0.3.0"}
