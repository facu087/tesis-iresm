"""
Router FastAPI — revisión admin de cuentas pendientes (Sprint 4, sección 5).

Se completa en la sección 5 de `tasks.md`; por ahora solo declara el router
para que `backend/main.py` pueda montarlo sin quedar a mitad de camino.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["admin"])
