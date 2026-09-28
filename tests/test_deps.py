"""
Tests de las dependencias FastAPI de sesión y autorización (tareas 2.3/5.1/6.1).

`requerir_sesion` exige una sesión válida (401 si falta); `requerir_admin`
exige además rol `admin` (403 si no); `requerir_medico_verificado` exige rol
`medico` + estado `verificado` (403 en cualquier otro caso, incluida una
cuenta `admin` sin cuenta de médico verificada).
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.auth.deps import get_session_dep, requerir_admin, requerir_medico_verificado, requerir_sesion
from backend.auth.sesiones import COOKIE_NAME, crear_sesion
from backend.models.cuenta import CuentaMedico, EstadoCuenta, RolCuenta


@pytest.fixture()
def engine():
    # `StaticPool` es necesario: `TestClient` ejecuta las dependencias sync
    # en un hilo del threadpool, y sin este pool una base `sqlite://` en
    # memoria es privada por hilo — perdería las filas creadas en el test.
    e = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(e)
    return e


@pytest.fixture()
def app_de_prueba(engine, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "clave-de-test-no-usar-en-produccion")

    def _get_session():
        with Session(engine) as session:
            yield session

    app = FastAPI()
    app.dependency_overrides[get_session_dep] = _get_session

    @app.get("/con-sesion")
    def _con_sesion(cuenta: CuentaMedico = Depends(requerir_sesion)):
        return {"email": cuenta.email}

    @app.get("/solo-admin")
    def _solo_admin(cuenta: CuentaMedico = Depends(requerir_admin)):
        return {"email": cuenta.email}

    @app.get("/solo-medico-verificado")
    def _solo_medico(cuenta: CuentaMedico = Depends(requerir_medico_verificado)):
        return {"email": cuenta.email}

    return app


@pytest.fixture()
def client(app_de_prueba):
    with TestClient(app_de_prueba) as c:
        yield c


def _cookie_para(engine, **kwargs) -> str:
    with Session(engine) as session:
        cuenta = CuentaMedico(email=kwargs.pop("email"), password_hash="x", **kwargs)
        session.add(cuenta)
        session.commit()
        session.refresh(cuenta)
        return crear_sesion(session, cuenta)


class TestRequerirSesion:
    def test_sin_cookie_devuelve_401(self, client):
        resp = client.get("/con-sesion")
        assert resp.status_code == 401

    def test_con_sesion_valida_identifica_la_cuenta(self, client, engine):
        token = _cookie_para(engine, email="ana@hospital.example")
        client.cookies.set(COOKIE_NAME, token)
        resp = client.get("/con-sesion")
        assert resp.status_code == 200
        assert resp.json()["email"] == "ana@hospital.example"


class TestRequerirAdmin:
    def test_medico_recibe_403(self, client, engine):
        token = _cookie_para(engine, email="ana@hospital.example", rol=RolCuenta.MEDICO)
        client.cookies.set(COOKIE_NAME, token)
        resp = client.get("/solo-admin")
        assert resp.status_code == 403

    def test_admin_accede(self, client, engine):
        token = _cookie_para(engine, email="admin@nexus.local", rol=RolCuenta.ADMIN)
        client.cookies.set(COOKIE_NAME, token)
        resp = client.get("/solo-admin")
        assert resp.status_code == 200


class TestRequerirMedicoVerificado:
    def test_sin_sesion_devuelve_401(self, client):
        resp = client.get("/solo-medico-verificado")
        assert resp.status_code == 401

    def test_medico_pendiente_devuelve_403(self, client, engine):
        token = _cookie_para(
            engine, email="ana@hospital.example", rol=RolCuenta.MEDICO, estado=EstadoCuenta.PENDIENTE
        )
        client.cookies.set(COOKIE_NAME, token)
        resp = client.get("/solo-medico-verificado")
        assert resp.status_code == 403

    def test_medico_rechazado_devuelve_403(self, client, engine):
        token = _cookie_para(
            engine, email="ana@hospital.example", rol=RolCuenta.MEDICO, estado=EstadoCuenta.RECHAZADO
        )
        client.cookies.set(COOKIE_NAME, token)
        resp = client.get("/solo-medico-verificado")
        assert resp.status_code == 403

    def test_admin_sin_cuenta_medico_verificada_devuelve_403(self, client, engine):
        token = _cookie_para(engine, email="admin@nexus.local", rol=RolCuenta.ADMIN)
        client.cookies.set(COOKIE_NAME, token)
        resp = client.get("/solo-medico-verificado")
        assert resp.status_code == 403

    def test_medico_verificado_accede(self, client, engine):
        token = _cookie_para(
            engine, email="ana@hospital.example", rol=RolCuenta.MEDICO, estado=EstadoCuenta.VERIFICADO
        )
        client.cookies.set(COOKIE_NAME, token)
        resp = client.get("/solo-medico-verificado")
        assert resp.status_code == 200
