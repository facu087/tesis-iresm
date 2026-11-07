"""
Demo — Limpieza automática de datos vencidos (tarjeta #56, Sprint 5).

La tarjeta pedía "un job que elimine archivos de sesión expirados". Antes de
escribir nada se verificó la premisa, y no se sostiene: el pipeline **no escribe
archivos temporales** (el PDF se procesa en memoria con `io.BytesIO` y el PDF del
reporte se devuelve en el cuerpo de la respuesta). Lo que sí se acumulaba sin
borrarse nunca eran las filas de la tabla `sesion`: dato personal —qué cuenta
inició sesión y cuándo— sobreviviendo indefinidamente a la sesión que lo
justificaba.

Este script muestra, en una base SQLite en memoria y sin red ni cuota:

  1. La premisa: qué escribe el backend a disco, buscado en el código fuente.
  2. Una base con sesiones de distintas edades, antes y después de la limpieza.
  3. Que la limpieza NO cambia el comportamiento observable: una sesión viva
     sigue resolviéndose y una vencida seguía sin resolverse.
  4. Que un fallo de la limpieza no tumba nada: devuelve `ok=False`.

Los reportes nunca llevan emails, tokens ni ids de cuenta: solo conteos.

    python scripts/demo_limpieza_temporales.py

Artefactos en output/demo_limpieza_temporales/:
    resultado.txt → la corrida completa
    resumen.json  → los números

Sale con código 1 si alguna de las comprobaciones falla.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "clave-demo-limpieza-no-usar-en-produccion")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")

_RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(_RAIZ))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from backend import db as db_module
from backend.auth.security import hash_password
from backend.auth.sesiones import crear_sesion, resolver_sesion
from backend.mantenimiento.limpieza import ejecutar_limpieza
from backend.models.cuenta import CuentaMedico, EstadoCuenta, RolCuenta
from backend.models.sesion import Sesion

_SEP = "═" * 78
_SUB = "─" * 78
_OUT_DIR = _RAIZ / "output" / "demo_limpieza_temporales"

# Patrones que delatan que se guarda algo a disco.
_ESCRITURAS = re.compile(
    r"tempfile|NamedTemporaryFile|mkstemp|TemporaryDirectory|"
    r"open\([^)]*['\"][wa]b?['\"]|write_text|write_bytes|\.save\("
)


def _escrituras_a_disco() -> list[str]:
    """Todo lo que el backend escribe a disco, fuera del módulo de limpieza."""
    halladas = []
    for archivo in sorted((_RAIZ / "backend").rglob("*.py")):
        relativo = archivo.relative_to(_RAIZ).as_posix()
        if "mantenimiento" in relativo or "__pycache__" in relativo:
            continue
        for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            if _ESCRITURAS.search(linea):
                halladas.append(f"{relativo}:{n}")
    return halladas


def main() -> None:
    lineas: list[str] = []
    resumen: dict = {}

    def emitir(texto: str = "") -> None:
        print(texto)
        lineas.append(texto)

    emitir(_SEP)
    emitir("DEMO — Limpieza automática de datos vencidos (tarjeta #56)")
    emitir(_SEP)

    # ── 1. La premisa de la tarjeta ──────────────────────────────────────────
    emitir(f"\n{_SUB}\n1. ¿Hay archivos temporales que limpiar?\n{_SUB}")
    escrituras = _escrituras_a_disco()
    emitir(f"  Escrituras a disco en backend/ (fuera del módulo de limpieza): {len(escrituras)}")
    for e in escrituras:
        emitir(f"      {e}")
    emitir("  Ninguna guarda el documento del paciente: son el grabador del modo mock y su")
    emitir("  regenerador (los abre solo un script) y la telemetría (solo conteos).")
    emitir("  El PDF subido se procesa en memoria: no queda archivo que borrar.")
    resumen["escrituras_a_disco"] = escrituras

    # ── 2. Sesiones de distintas edades ──────────────────────────────────────
    emitir(f"\n{_SUB}\n2. Lo que sí se acumulaba: filas de la tabla `sesion`\n{_SUB}")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db_module.set_engine(engine)
    db_module.create_db_and_tables(bind=engine)

    ahora = datetime.now(timezone.utc)
    escenarios = [  # (etiqueta, minutos hasta vencer; negativo = ya venció)
        ("venció hace 30 días", -30 * 24 * 60),
        ("venció hace 1 día", -24 * 60),
        ("venció hace 1 segundo", -1 / 60),
        ("vence en este instante", 0),
        ("vence en 1 minuto", 1),
        ("vence en 1 hora", 60),
    ]

    with Session(engine) as s:
        cuenta = CuentaMedico(
            nombre="Ana", apellido="Demo", dni="30111222", matricula="12345",
            jurisdiccion="Córdoba", email="demo@limpieza.example",
            password_hash=hash_password("ContraseñaDeDemo123"),
            rol=RolCuenta.MEDICO, estado=EstadoCuenta.VERIFICADO)
        s.add(cuenta)
        s.commit()
        s.refresh(cuenta)

        cookies = {}
        for etiqueta, minutos in escenarios:
            cookie = crear_sesion(s, cuenta, ahora=ahora)
            token = cookie.split(".")[0]
            fila = s.get(Sesion, token)
            fila.expira_en = ahora + timedelta(minutes=minutos)
            s.add(fila)
            cookies[etiqueta] = cookie
        s.commit()

        total_antes = len(s.exec(select(Sesion)).all())
        resolvibles_antes = {
            e: resolver_sesion(s, c) is not None for e, c in cookies.items()}

    emitir(f"\n  Sesiones en la base ANTES: {total_antes}\n")
    emitir(f"  {'sesión':28} {'¿se resolvía?':>14}")
    for etiqueta, _ in escenarios:
        emitir(f"  {etiqueta:28} {'sí' if resolvibles_antes[etiqueta] else 'no':>14}")

    # ── 3. La limpieza ───────────────────────────────────────────────────────
    emitir(f"\n{_SUB}\n3. Se corre la limpieza\n{_SUB}")
    resultado = ejecutar_limpieza(engine=engine, ahora=ahora)
    emitir(f"  ok: {resultado.ok}   borradas: {resultado.sesiones_expiradas_borradas}"
           f"   duración: {resultado.duracion_segundos:.4f}s")

    with Session(engine) as s:
        total_despues = len(s.exec(select(Sesion)).all())
        resolvibles_despues = {
            e: resolver_sesion(s, c) is not None for e, c in cookies.items()}
        sobreviven = {e: s.get(Sesion, c.split(".")[0]) is not None for e, c in cookies.items()}

    emitir(f"\n  Sesiones en la base DESPUÉS: {total_despues}\n")
    emitir(f"  {'sesión':28} {'¿sigue en la base?':>20} {'¿se resuelve?':>15}")
    for etiqueta, _ in escenarios:
        emitir(f"  {etiqueta:28} {'sí' if sobreviven[etiqueta] else 'BORRADA':>20}"
               f" {'sí' if resolvibles_despues[etiqueta] else 'no':>15}")

    vencidas = [e for e, m in escenarios if m <= 0]
    vivas = [e for e, m in escenarios if m > 0]
    borro_exacto_lo_vencido = all(not sobreviven[e] for e in vencidas)
    no_toco_ninguna_viva = all(sobreviven[e] for e in vivas)
    comportamiento_igual = resolvibles_antes == resolvibles_despues

    # ── 4. Un fallo no tumba nada ────────────────────────────────────────────
    emitir(f"\n{_SUB}\n4. Una limpieza que falla no rompe nada\n{_SUB}")
    roto = create_engine("sqlite://")  # sin tablas: la pasada va a fallar
    fallida = ejecutar_limpieza(engine=roto, ahora=ahora)
    emitir(f"  ok: {fallida.ok}   fallo: {fallida.fallo}   borradas: "
           f"{fallida.sesiones_expiradas_borradas}")
    emitir("  No levantó excepción: el backend sigue y se reintenta en la próxima pasada.")
    emitir("  El log informa el TIPO de la excepción, nunca su mensaje.")

    comprobaciones = {
        "borra exactamente lo vencido (incluida la que vence ahora)": borro_exacto_lo_vencido,
        "no toca ninguna sesión viva": no_toco_ninguna_viva,
        "el comportamiento observable no cambia": comportamiento_igual,
        "un fallo devuelve ok=False sin levantar": (not fallida.ok and fallida.fallo is not None),
    }
    todo_ok = all(comprobaciones.values())

    emitir(f"\n{_SEP}")
    for texto, ok in comprobaciones.items():
        emitir(f"{'[OK]' if ok else '[X]'} {texto}")
    emitir(_SEP)

    resumen.update({
        "sesiones_antes": total_antes, "sesiones_despues": total_despues,
        "borradas": resultado.sesiones_expiradas_borradas,
        "comprobaciones": comprobaciones,
    })
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "resultado.txt").write_text("\n".join(lineas), encoding="utf-8")
    (_OUT_DIR / "resumen.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nArtefactos: {_OUT_DIR}")
    sys.exit(0 if todo_ok else 1)


if __name__ == "__main__":
    main()
