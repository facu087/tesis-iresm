"""
Tests de los modelos de auditoría (`DecisionAuditoria`) y sesión (`Sesion`).

Ambos se crean y consultan contra una base SQLite temporal en memoria, junto
con la `CuentaMedico` que referencian.
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from backend.models.auditoria import DecisionAuditoria, DecisionTipo
from backend.models.cuenta import CuentaMedico, RolCuenta
from backend.models.sesion import Sesion


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _crear_cuentas(session: Session) -> tuple[CuentaMedico, CuentaMedico]:
    admin = CuentaMedico(email="admin@nexus.local", password_hash="x", rol=RolCuenta.ADMIN)
    medico = CuentaMedico(
        nombre="Ana",
        apellido="Pérez",
        dni="1",
        matricula="2",
        jurisdiccion="Córdoba",
        email="ana@hospital.example",
        password_hash="x",
    )
    session.add(admin)
    session.add(medico)
    session.commit()
    session.refresh(admin)
    session.refresh(medico)
    return admin, medico


def test_registrar_y_consultar_decision_de_auditoria():
    engine = _engine()
    with Session(engine) as session:
        admin, medico = _crear_cuentas(session)
        admin_id, cuenta_id = admin.id, medico.id
        decision = DecisionAuditoria(
            admin_id=admin_id,
            cuenta_id=cuenta_id,
            decision=DecisionTipo.APROBADO,
            motivo="Coincide con el Buscador Nacional REFEPS.",
            fuente_consultada="REFEPS",
        )
        session.add(decision)
        session.commit()
        session.refresh(decision)
        assert decision.id is not None
        assert decision.decidida_en is not None

    with Session(engine) as session:
        recuperada = session.exec(
            select(DecisionAuditoria).where(DecisionAuditoria.cuenta_id == cuenta_id)
        ).one()
        assert recuperada.decision == DecisionTipo.APROBADO
        assert recuperada.admin_id == admin_id
        assert recuperada.fuente_consultada == "REFEPS"


def test_crear_y_consultar_sesion():
    engine = _engine()
    with Session(engine) as session:
        _, medico = _crear_cuentas(session)
        cuenta_id = medico.id
        ahora = datetime.now(timezone.utc)
        sesion = Sesion(
            id="token-opaco-aleatorio",
            cuenta_id=cuenta_id,
            creada_en=ahora,
            expira_en=ahora + timedelta(minutes=60),
        )
        session.add(sesion)
        session.commit()

    with Session(engine) as session:
        recuperada = session.get(Sesion, "token-opaco-aleatorio")
        assert recuperada is not None
        assert recuperada.cuenta_id == cuenta_id
        assert recuperada.expira_en > recuperada.creada_en
