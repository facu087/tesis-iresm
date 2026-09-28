"""
Punto de entrada de la aplicación FastAPI — NEXUS.

Arrancar con:
    uvicorn backend.main:app --reload
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware

from .api.admin_router import router as admin_router
from .api.cuentas_router import router as cuentas_router
from .api.router import router
from .db import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Crea el esquema de la base de cuentas si no existe (design.md — D1)."""
    create_db_and_tables()
    yield


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
    lifespan=lifespan,
)

_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cuentas_router)
app.include_router(admin_router)
app.include_router(router)


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    """Verificación de estado del servicio."""
    return {"status": "ok", "service": "NEXUS", "version": "0.3.0"}
