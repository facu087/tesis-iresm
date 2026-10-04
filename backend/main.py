"""
Punto de entrada de la aplicación FastAPI — NEXUS.

Arrancar con:
    uvicorn backend.main:app --reload
"""

import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware

from .api.router import router
from .mock.mode import ENV_VAR as _MOCK_ENV_VAR
from .mock.mode import is_mock_active

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
    docs_url="/docs",
    redoc_url="/redoc",
)

_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    """Verificación de estado del servicio."""
    return {"status": "ok", "service": "NEXUS", "version": "0.3.0"}
