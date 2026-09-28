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


def test_levantar_la_app_crea_el_esquema_en_el_engine_activo(tmp_path):
    """
    El `lifespan` de la app llama a `create_db_and_tables()` sin argumentos:
    usa el engine activo del módulo. `tests/conftest.py` ya lo reemplaza por
    uno en memoria antes de cada test (fixture autouse) — acá solo se
    confirma que, dado un engine en blanco, levantar la app crea el esquema.

    Se usa un archivo real (no `:memory:`): `TestClient` corre el lifespan en
    otro hilo, y una base `:memory:` sin `StaticPool` es privada por hilo —
    un archivo en disco no tiene ese problema.
    """
    from backend import db as db_module

    db_path = tmp_path / "arranque" / "nexus_test.db"
    engine_en_blanco = build_engine(str(db_path))
    original = db_module.engine
    db_module.set_engine(engine_en_blanco)
    try:
        from fastapi.testclient import TestClient

        from backend.main import app

        with TestClient(app):
            pass

        assert "cuenta_medico" in inspect(engine_en_blanco).get_table_names()
    finally:
        db_module.set_engine(original)
