"""
Tests del motor de base de datos y el arranque de la app (tarea 1.4).

`resolve_db_path()` lee `NEXUS_DB_PATH` en cada llamada (no al importar el
módulo), así que estos tests pueden fijarla con `monkeypatch` sin depender
del orden de import. `create_db_and_tables()` crea el directorio contenedor
si hace falta y las tablas del esquema completo.
"""

from sqlalchemy import inspect

from backend.db import build_engine, create_db_and_tables, resolve_db_path


def test_resolve_db_path_usa_la_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("NEXUS_DB_PATH", "/tmp/algo/nexus.db")
    assert resolve_db_path() == "/tmp/algo/nexus.db"


def test_resolve_db_path_tiene_default_gitignoreado(monkeypatch):
    monkeypatch.delenv("NEXUS_DB_PATH", raising=False)
    assert resolve_db_path() == "./data/nexus.db"


def test_create_db_and_tables_crea_el_archivo_y_las_tablas(tmp_path):
    db_path = tmp_path / "sub" / "nexus_test.db"
    assert not db_path.exists()

    engine = build_engine(str(db_path))
    create_db_and_tables(bind=engine)

    assert db_path.exists()
    tablas = set(inspect(engine).get_table_names())
    assert {"cuenta_medico", "decision_auditoria", "sesion"} <= tablas


# El test que confirma que el `lifespan` de `backend.main` dispara
# `create_db_and_tables()` al levantar la app vive en este mismo archivo,
# agregado en el commit que cablea ese `lifespan` (sección 2 de tasks.md) —
# acá arriba solo lo que no depende de `backend.main`.
