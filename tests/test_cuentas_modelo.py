"""
Tests del modelo de cuenta de médico (`CuentaMedico`) — SQLModel.

Verifica que el modelo se puede instanciar y persistir en una base SQLite
temporal en memoria, que nace con los defaults esperados por el diseño
(estado `pendiente`, rol `medico`, `email_verificado` en `False`) y que la
combinación matrícula + jurisdicción es única a nivel de base de datos.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from backend.models.cuenta import CuentaMedico, EstadoCuenta, RolCuenta


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def test_crear_y_persistir_cuenta_medico():
    engine = _engine()
    cuenta = CuentaMedico(
        nombre="Ana",
        apellido="Pérez",
        dni="30111222",
        matricula="12345",
        jurisdiccion="Córdoba",
        email="ana.perez@hospital.example",
        password_hash="hash-no-en-texto-plano",
        consentimiento_en=datetime.now(timezone.utc),
    )
    with Session(engine) as session:
        session.add(cuenta)
        session.commit()
        session.refresh(cuenta)
        assert cuenta.id is not None

    with Session(engine) as session:
        recuperada = session.exec(
            select(CuentaMedico).where(CuentaMedico.email == "ana.perez@hospital.example")
        ).one()
        assert recuperada.dni == "30111222"
        assert recuperada.rol == RolCuenta.MEDICO
        assert recuperada.estado == EstadoCuenta.PENDIENTE
        assert recuperada.email_verificado is False


def test_profesion_es_opcional():
    cuenta = CuentaMedico(
        nombre="Bruno",
        apellido="Diaz",
        dni="1",
        matricula="2",
        jurisdiccion="CABA",
        email="bruno@hospital.example",
        password_hash="x",
    )
    assert cuenta.profesion is None


def test_admin_no_requiere_matricula_ni_dni():
    """Alta del primer admin (CLI): el modelo debe permitir estos campos vacíos."""
    engine = _engine()
    admin = CuentaMedico(
        email="admin@nexus.local",
        password_hash="x",
        rol=RolCuenta.ADMIN,
        estado=EstadoCuenta.VERIFICADO,
    )
    with Session(engine) as session:
        session.add(admin)
        session.commit()
        session.refresh(admin)
        assert admin.id is not None
        assert admin.dni is None
        assert admin.matricula is None


def test_matricula_y_jurisdiccion_duplicada_falla_a_nivel_de_base():
    engine = _engine()
    c1 = CuentaMedico(
        nombre="A",
        apellido="B",
        dni="1",
        matricula="999",
        jurisdiccion="Córdoba",
        email="a@hospital.example",
        password_hash="x",
    )
    c2 = CuentaMedico(
        nombre="C",
        apellido="D",
        dni="2",
        matricula="999",
        jurisdiccion="Córdoba",
        email="c@hospital.example",
        password_hash="x",
    )
    with Session(engine) as session:
        session.add(c1)
        session.commit()

    with Session(engine) as session:
        session.add(c2)
        with pytest.raises(IntegrityError):
            session.commit()


def test_dos_admins_sin_matricula_no_chocan_entre_si():
    """NULL no es igual a NULL en SQLite: dos cuentas sin matrícula conviven."""
    engine = _engine()
    a1 = CuentaMedico(email="admin1@nexus.local", password_hash="x", rol=RolCuenta.ADMIN)
    a2 = CuentaMedico(email="admin2@nexus.local", password_hash="x", rol=RolCuenta.ADMIN)
    with Session(engine) as session:
        session.add(a1)
        session.add(a2)
        session.commit()
        assert a1.id is not None
        assert a2.id is not None
