"""
Motor de base de datos SQLite — capa de persistencia de cuentas (Sprint 4).

Sin Alembic todavía (design.md — D1): el esquema se crea con
`SQLModel.metadata.create_all()` al levantar la app. La ruta del archivo sale
de `NEXUS_DB_PATH` (`.env`), con default `./data/nexus.db`, gitignoreado como
`chroma_db/`.

`resolve_db_path()` lee la variable de entorno en cada llamada — no la fija
al importar el módulo — para que los tests puedan controlarla con
`monkeypatch` sin depender del orden de import. El engine sigue siendo un
único objeto a nivel de módulo (`engine`) para reutilizar el pool de
conexiones entre requests; `set_engine()` existe para que los tests lo
reemplacen por uno en memoria antes de que el `lifespan` de la app lo use.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

_DB_PATH_ENV = "NEXUS_DB_PATH"
_DEFAULT_DB_PATH = "./data/nexus.db"


def resolve_db_path() -> str:
    """Ruta del archivo SQLite: `NEXUS_DB_PATH` o el default gitignoreado."""
    return os.getenv(_DB_PATH_ENV, _DEFAULT_DB_PATH)


def build_engine(db_path: str | None = None) -> Engine:
    """
    Construye un engine de SQLAlchemy para `db_path` (o la ruta resuelta del
    entorno). `create_engine()` es perezoso: no toca el disco hasta la
    primera conexión real, así que solo importar este módulo no crea nada.
    """
    path = db_path if db_path is not None else resolve_db_path()
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


engine: Engine = build_engine()


def set_engine(new_engine: Engine) -> None:
    """Reemplaza el engine activo. Lo usan los tests para aislar la base."""
    global engine
    engine = new_engine


def create_db_and_tables(bind: Engine | None = None) -> None:
    """
    Crea el esquema si no existe, en `bind` o en el engine activo del módulo.

    Importa los módulos de modelos para que queden registrados en
    `SQLModel.metadata` antes de `create_all()` — si ninguno se importó
    todavía en este proceso, `create_all()` no vería sus tablas.
    """
    from .models import auditoria, cuenta, sesion  # noqa: F401

    target = bind if bind is not None else engine

    url = target.url
    if url.get_backend_name() == "sqlite" and url.database not in (None, ":memory:"):
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    SQLModel.metadata.create_all(target)


def get_session() -> Generator[Session, None, None]:
    """Dependencia FastAPI: una sesión de base de datos por request."""
    with Session(engine) as session:
        yield session
