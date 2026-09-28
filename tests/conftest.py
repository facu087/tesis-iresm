"""
Fixtures compartidas de toda la suite (Sprint 4 — registro de médicos).

La fixture `_base_de_datos_temporal` es `autouse`: reemplaza el engine
activo de `backend.db` por uno SQLite en memoria antes de CADA test y lo
restaura después. Es necesaria incluso para tests que no tocan cuentas,
porque cualquiera que instancie `TestClient(app)` dispara el `lifespan` de
la app y, con él, `create_db_and_tables()` — sin este reemplazo, correr la
suite escribiría en la base real del proyecto (`./data/nexus.db`).

`StaticPool` es obligatorio para el engine en memoria: `TestClient` ejecuta
las dependencias síncronas en un hilo del threadpool, y una base
`sqlite://` en memoria es privada por hilo sin ese pool — perdería entre
request y request las filas creadas en el test.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from backend import db as db_module
from backend.auth.security import hash_password
from backend.models.cuenta import CuentaMedico, EstadoCuenta, RolCuenta

_ORIGEN_PERMITIDO = "http://localhost:3000"


@pytest.fixture(autouse=True)
def _base_de_datos_temporal(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "clave-de-test-no-usar-en-produccion")
    monkeypatch.setenv("ALLOWED_ORIGINS", _ORIGEN_PERMITIDO)
    os.environ.setdefault("SESSION_TTL_MINUTES", "60")

    original = db_module.engine
    engine_temporal = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db_module.set_engine(engine_temporal)
    db_module.create_db_and_tables(bind=engine_temporal)
    yield engine_temporal
    db_module.set_engine(original)


@pytest.fixture()
def client():
    """Cliente HTTP con el `Origin` permitido ya seteado por default."""
    from backend.main import app

    with TestClient(app, headers={"Origin": _ORIGEN_PERMITIDO}) as c:
        yield c


@pytest.fixture()
def cuenta_medico_verificada(_base_de_datos_temporal):
    """Cuenta de médico en estado `verificado`, ya persistida."""
    with Session(_base_de_datos_temporal) as session:
        cuenta = CuentaMedico(
            nombre="Ana",
            apellido="Pérez",
            dni="30111222",
            matricula="12345",
            jurisdiccion="Córdoba",
            email="medico.verificado@hospital.example",
            password_hash=hash_password("ContraseñaSegura123"),
            rol=RolCuenta.MEDICO,
            estado=EstadoCuenta.VERIFICADO,
        )
        session.add(cuenta)
        session.commit()
        session.refresh(cuenta)
        session.expunge(cuenta)
        return cuenta


@pytest.fixture()
def client_medico_verificado(client, cuenta_medico_verificada):
    """Cliente ya logueado como médico verificado (cookie de sesión activa)."""
    resp = client.post(
        "/api/login",
        json={"email": cuenta_medico_verificada.email, "password": "ContraseñaSegura123"},
    )
    assert resp.status_code == 200, resp.text
    return client


@pytest.fixture()
def cuenta_medico_pendiente(_base_de_datos_temporal):
    """Cuenta de médico recién registrada, en estado `pendiente`."""
    with Session(_base_de_datos_temporal) as session:
        cuenta = CuentaMedico(
            nombre="Bruno",
            apellido="Diaz",
            dni="30999888",
            matricula="54321",
            jurisdiccion="CABA",
            email="medico.pendiente@hospital.example",
            password_hash=hash_password("ContraseñaSegura123"),
            rol=RolCuenta.MEDICO,
            estado=EstadoCuenta.PENDIENTE,
        )
        session.add(cuenta)
        session.commit()
        session.refresh(cuenta)
        session.expunge(cuenta)
        return cuenta


@pytest.fixture()
def cuenta_admin(_base_de_datos_temporal):
    """Cuenta con rol `admin`, ya persistida."""
    with Session(_base_de_datos_temporal) as session:
        admin = CuentaMedico(
            email="admin@nexus.local",
            password_hash=hash_password("ContraseñaAdmin123"),
            rol=RolCuenta.ADMIN,
            estado=EstadoCuenta.VERIFICADO,
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        session.expunge(admin)
        return admin


@pytest.fixture()
def client_admin(client, cuenta_admin):
    """Cliente ya logueado como admin (cookie de sesión activa)."""
    resp = client.post(
        "/api/login", json={"email": cuenta_admin.email, "password": "ContraseñaAdmin123"}
    )
    assert resp.status_code == 200, resp.text
    return client
