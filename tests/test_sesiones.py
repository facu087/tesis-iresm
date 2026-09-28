"""
Tests de la sesión de servidor (tarea 2.3, design.md D3).

Una sesión identifica a la cuenta en solicitudes posteriores, expira pasado
`SESSION_TTL_MINUTES` y el logout la invalida. La fuente de verdad es la fila
en `Sesion`, no la firma de la cookie (design.md D3): `resolver_sesion`
también debe rechazar un valor de cookie manipulado.
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from backend.auth.sesiones import COOKIE_NAME, crear_sesion, invalidar_sesion, resolver_sesion
from backend.models.cuenta import CuentaMedico, RolCuenta


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _crear_cuenta(session: Session) -> CuentaMedico:
    cuenta = CuentaMedico(email="ana@hospital.example", password_hash="x", rol=RolCuenta.MEDICO)
    session.add(cuenta)
    session.commit()
    session.refresh(cuenta)
    return cuenta


def test_crear_sesion_y_resolverla_identifica_la_cuenta(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "clave-de-test-no-usar-en-produccion")
    monkeypatch.setenv("SESSION_TTL_MINUTES", "60")
    engine = _engine()
    with Session(engine) as session:
        cuenta = _crear_cuenta(session)
        valor_cookie = crear_sesion(session, cuenta)

        resuelta = resolver_sesion(session, valor_cookie)
        assert resuelta is not None
        assert resuelta.id == cuenta.id


def test_resolver_sesion_con_valor_manipulado_devuelve_none(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "clave-de-test-no-usar-en-produccion")
    engine = _engine()
    with Session(engine) as session:
        cuenta = _crear_cuenta(session)
        valor_cookie = crear_sesion(session, cuenta)

        manipulado = valor_cookie[:-1] + ("a" if valor_cookie[-1] != "a" else "b")
        assert resolver_sesion(session, manipulado) is None


def test_resolver_sesion_expirada_devuelve_none(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "clave-de-test-no-usar-en-produccion")
    engine = _engine()
    with Session(engine) as session:
        cuenta = _crear_cuenta(session)
        valor_cookie = crear_sesion(session, cuenta, ahora=datetime.now(timezone.utc) - timedelta(minutes=120))

        assert resolver_sesion(session, valor_cookie) is None


def test_invalidar_sesion_la_deja_sin_efecto(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "clave-de-test-no-usar-en-produccion")
    engine = _engine()
    with Session(engine) as session:
        cuenta = _crear_cuenta(session)
        valor_cookie = crear_sesion(session, cuenta)
        assert resolver_sesion(session, valor_cookie) is not None

        invalidar_sesion(session, valor_cookie)
        assert resolver_sesion(session, valor_cookie) is None


def test_cookie_name_esta_definido():
    assert isinstance(COOKIE_NAME, str) and COOKIE_NAME
