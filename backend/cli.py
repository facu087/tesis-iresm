"""
CLI de administración de NEXUS — alta del primer administrador (Sprint 4).

`revision-admin-matriculas` — Requirement: Alta del primer administrador. Sin
usuario ni contraseña por defecto: las credenciales siempre las provee quien
ejecuta el comando, por parámetro o de forma interactiva (sin eco en la
terminal).

Uso:
    python -m backend.cli crear-admin --email admin@nexus.local
    python -m backend.cli crear-admin --email admin@nexus.local --password "..."
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Sequence

from sqlalchemy import Engine
from sqlmodel import Session, select

from .auth.security import hash_password
from .db import create_db_and_tables, engine as _engine_activo
from .models.cuenta import CuentaMedico, EstadoCuenta, RolCuenta


def crear_admin(email: str, password: str, *, engine_: Engine | None = None) -> CuentaMedico:
    """
    Crea la primera cuenta administradora. Falla si ya existe una cuenta con
    ese email — no distingue entre "ya hay un admin" y "el email está
    ocupado": cualquiera de los dos es motivo suficiente para no crear una
    cuenta nueva.
    """
    motor = engine_ if engine_ is not None else _engine_activo
    create_db_and_tables(bind=motor)
    with Session(motor) as session:
        existente = session.exec(select(CuentaMedico).where(CuentaMedico.email == email)).first()
        if existente is not None:
            raise ValueError(f"Ya existe una cuenta con el email {email}.")

        admin = CuentaMedico(
            email=email,
            password_hash=hash_password(password),
            rol=RolCuenta.ADMIN,
            estado=EstadoCuenta.VERIFICADO,
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        return admin


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.cli")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    crear = subparsers.add_parser(
        "crear-admin", help="Crea la primera cuenta administradora (uso único)."
    )
    crear.add_argument("--email", required=True, help="Email institucional de la cuenta admin.")
    crear.add_argument(
        "--password",
        default=None,
        help="Si se omite, se pide de forma interactiva (sin eco en la terminal).",
    )

    args = parser.parse_args(argv)

    if args.comando == "crear-admin":
        password = args.password or getpass.getpass("Contraseña para la cuenta admin: ")
        if not password:
            print("La contraseña no puede estar vacía.", file=sys.stderr)
            return 1
        try:
            admin = crear_admin(args.email, password)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Cuenta admin creada: {admin.email} (id={admin.id})")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
