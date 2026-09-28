"""
Tests de `POST /api/registro` (alta) y `PUT /api/registro` (reenvío tras un
rechazo) — tareas 3.1, 4.1, 4.2, 4.3 y 4.4.
"""

from datetime import datetime, timezone

from sqlmodel import Session, select

from backend.auth.security import hash_password
from backend.models.cuenta import CuentaMedico, EstadoCuenta, RolCuenta


def _payload(**overrides) -> dict:
    base = {
        "nombre": "Carla",
        "apellido": "Gómez",
        "dni": "28555444",
        "matricula": "9988",
        "jurisdiccion": "Córdoba",
        "profesion": "Neurología",
        "email": "carla.gomez@hospital.example",
        "password": "ContraseñaSegura123",
        "acepta_tratamiento_datos": True,
    }
    base.update(overrides)
    return base


class TestRegistroExitoso:
    def test_registro_completo_crea_cuenta_pendiente(self, client):
        resp = client.post("/api/registro", json=_payload())
        assert resp.status_code == 201
        assert resp.json()["estado"] == "pendiente"
        assert resp.json()["rol"] == "medico"

    def test_profesion_es_opcional(self, client):
        payload = _payload(email="sin.profesion@hospital.example", dni="1", matricula="2")
        del payload["profesion"]
        resp = client.post("/api/registro", json=payload)
        assert resp.status_code == 201


class TestCamposObligatorios:
    def test_falta_matricula_rechaza_sin_crear_cuenta(self, client, _base_de_datos_temporal):
        payload = _payload()
        del payload["matricula"]
        resp = client.post("/api/registro", json=payload)
        assert resp.status_code == 422

        with Session(_base_de_datos_temporal) as session:
            assert session.exec(select(CuentaMedico)).first() is None


class TestConsentimiento:
    def test_sin_consentimiento_rechaza_sin_crear_cuenta(self, client, _base_de_datos_temporal):
        resp = client.post("/api/registro", json=_payload(acepta_tratamiento_datos=False))
        assert resp.status_code == 422
        with Session(_base_de_datos_temporal) as session:
            assert session.exec(select(CuentaMedico)).first() is None

    def test_consentimiento_registra_fecha_y_hora(self, client, _base_de_datos_temporal):
        client.post("/api/registro", json=_payload())
        with Session(_base_de_datos_temporal) as session:
            cuenta = session.exec(select(CuentaMedico)).one()
            assert cuenta.consentimiento_en is not None


class TestUnicidad:
    def test_dni_duplicado_rechaza(self, client):
        client.post("/api/registro", json=_payload())
        resp = client.post(
            "/api/registro", json=_payload(email="otro@hospital.example", matricula="otra-mat")
        )
        assert resp.status_code == 409

    def test_matricula_y_jurisdiccion_duplicada_rechaza(self, client):
        client.post("/api/registro", json=_payload())
        resp = client.post(
            "/api/registro", json=_payload(email="otro2@hospital.example", dni="otro-dni")
        )
        assert resp.status_code == 409


class TestConsultaDeEstado:
    def test_medico_pendiente_consulta_su_estado(self, client):
        client.post("/api/registro", json=_payload())
        client.post(
            "/api/login", json={"email": _payload()["email"], "password": "ContraseñaSegura123"}
        )
        resp = client.get("/api/cuenta")
        assert resp.json()["estado"] == "pendiente"

    def test_medico_rechazado_ve_el_motivo(self, client, _base_de_datos_temporal):
        with Session(_base_de_datos_temporal) as session:
            cuenta = CuentaMedico(
                nombre="Diego",
                apellido="Ruiz",
                dni="1",
                matricula="2",
                jurisdiccion="CABA",
                email="rechazado@hospital.example",
                password_hash=hash_password("ContraseñaSegura123"),
                rol=RolCuenta.MEDICO,
                estado=EstadoCuenta.RECHAZADO,
                motivo_rechazo="Los datos no coinciden con el buscador público.",
            )
            session.add(cuenta)
            session.commit()

        client.post(
            "/api/login", json={"email": "rechazado@hospital.example", "password": "ContraseñaSegura123"}
        )
        resp = client.get("/api/cuenta")
        assert resp.json()["estado"] == "rechazado"
        assert resp.json()["motivo_rechazo"] == "Los datos no coinciden con el buscador público."


class TestReenvioTrasRechazo:
    def test_ciclo_completo_rechazo_correccion_pendiente(self, client, _base_de_datos_temporal):
        with Session(_base_de_datos_temporal) as session:
            cuenta = CuentaMedico(
                nombre="Diego",
                apellido="Ruiz",
                dni="1",
                matricula="2",
                jurisdiccion="CABA",
                email="rechazado2@hospital.example",
                password_hash=hash_password("ContraseñaSegura123"),
                rol=RolCuenta.MEDICO,
                estado=EstadoCuenta.RECHAZADO,
                motivo_rechazo="Matrícula no coincide.",
            )
            session.add(cuenta)
            session.commit()

        client.post(
            "/api/login", json={"email": "rechazado2@hospital.example", "password": "ContraseñaSegura123"}
        )
        resp = client.put(
            "/api/registro",
            json=_payload(email="rechazado2@hospital.example", dni="1", matricula="2"),
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] == "pendiente"
        assert resp.json()["motivo_rechazo"] is None


class TestValidacionDeOrigenEnRegistro:
    def test_origen_ajeno_rechaza_sin_crear_cuenta(self, client, _base_de_datos_temporal):
        resp = client.post(
            "/api/registro",
            json=_payload(),
            headers={"Origin": "https://sitio-ajeno.example"},
        )
        assert resp.status_code == 403
        with Session(_base_de_datos_temporal) as session:
            assert session.exec(select(CuentaMedico)).first() is None


class TestSinDatosClinicos:
    def test_el_modelo_de_cuenta_no_declara_campos_clinicos(self):
        """`registro-medicos` — Requirement: Sin datos clínicos en el registro de cuentas."""
        campos = set(CuentaMedico.model_fields.keys())
        prohibidos = {
            "raw_text",
            "clinical_text",
            "case_text",
            "report",
            "reporte",
            "hypotheses",
            "hipotesis",
            "pico",
            "biomarkers",
            "texto_clinico",
        }
        assert campos.isdisjoint(prohibidos)

    def test_el_almacenamiento_no_contiene_texto_clinico_de_pacientes(
        self, client, _base_de_datos_temporal
    ):
        client.post("/api/registro", json=_payload())
        with Session(_base_de_datos_temporal) as session:
            cuenta = session.exec(select(CuentaMedico)).one()
            valores = " ".join(
                str(v) for v in cuenta.model_dump().values() if v is not None
            )
            assert "neuropatía" not in valores.lower()
            assert "paciente" not in valores.lower()
