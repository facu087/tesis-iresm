"""
Tests de la validación de origen — mitigación CSRF (tarea 3.1, design.md D3).

Se ejercita `validar_origen` como dependencia FastAPI sobre una ruta mínima
armada en el propio test, para no acoplar este test a ningún endpoint real
todavía. Los endpoints reales la aplican en tareas 3.2/4/5/6.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.auth.origen import validar_origen


@pytest.fixture()
def app_de_prueba(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000,https://nexus.example")
    app = FastAPI()

    @app.post("/probar", dependencies=[Depends(validar_origen)])
    def _probar():
        return {"ok": True}

    return app


@pytest.fixture()
def client(app_de_prueba):
    with TestClient(app_de_prueba) as c:
        yield c


def test_origen_permitido_deja_pasar(client):
    resp = client.post("/probar", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200


def test_origen_ajeno_rechaza_con_403(client):
    resp = client.post("/probar", headers={"Origin": "https://sitio-ajeno.example"})
    assert resp.status_code == 403


def test_sin_origin_ni_referer_rechaza_con_403(client):
    resp = client.post("/probar")
    assert resp.status_code == 403


def test_referer_permitido_como_respaldo_cuando_falta_origin(client):
    resp = client.post(
        "/probar", headers={"Referer": "http://localhost:3000/registro"}
    )
    assert resp.status_code == 200


def test_referer_ajeno_como_respaldo_rechaza(client):
    resp = client.post(
        "/probar", headers={"Referer": "https://sitio-ajeno.example/algo"}
    )
    assert resp.status_code == 403


def test_origin_tiene_prioridad_sobre_referer(client):
    """Un Origin ajeno rechaza aunque el Referer sea uno permitido."""
    resp = client.post(
        "/probar",
        headers={
            "Origin": "https://sitio-ajeno.example",
            "Referer": "http://localhost:3000/registro",
        },
    )
    assert resp.status_code == 403
