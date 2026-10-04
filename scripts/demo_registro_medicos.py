"""
Demo de verificación — Registro de médicos, revisión admin y protección del pipeline.

Recorre el flujo completo del cambio `registro-medicos-matricula` contra una
base SQLite TEMPORAL (nunca toca `./data/nexus.db`) y SIN ninguna llamada a
un LLM real: las etapas del pipeline que llamarían a Groq/PubMed quedan
mockeadas, igual que en `tests/test_api.py`.

Recorrido:
    1. Se registran dos médicos (A y B), ambos quedan `pendiente`.
    2. A intenta analizar un caso -> 403 (todavía no está verificado).
    3. Se da de alta el primer admin por CLI (`backend.cli.crear_admin`).
    4. El admin lista pendientes y aprueba a B, indicando la fuente
       consultada -> queda `verificado` y se genera un `DecisionAuditoria`.
    5. B analiza un caso -> 200 (pipeline mockeado, cero llamadas a un LLM).
    6. El admin rechaza a A con un motivo -> queda `rechazado`, motivo
       visible, y se genera otro `DecisionAuditoria`.
    7. A corrige sus datos y reenvía el registro -> vuelve a `pendiente`.

Artefactos generados en output/demo_registro/:
    1. flujo.json    -> estado de ambas cuentas y de la auditoría en cada paso
    2. resumen.txt    -> narrativa legible del recorrido, paso a paso

Uso:
    python3 scripts/demo_registro_medicos.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import os

os.environ.setdefault("SECRET_KEY", "clave-demo-registro-no-usar-en-produccion")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from backend import db as db_module
from backend.cli import crear_admin
from backend.main import app

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_registro"
_ORIGIN = "http://localhost:3000"

_MEDICO_A = {
    "nombre": "Diego",
    "apellido": "Ruiz",
    "dni": "30555444",
    "matricula": "77001",
    "jurisdiccion": "CABA",
    "profesion": "Clínica Médica",
    "email": "diego.ruiz@hospital-demo.example",
    "password": "ContraseñaSegura123",
    "acepta_tratamiento_datos": True,
}
_MEDICO_B = {
    "nombre": "Ana",
    "apellido": "Pérez",
    "dni": "30111222",
    "matricula": "12345",
    "jurisdiccion": "Córdoba",
    "profesion": "Neurología",
    "email": "ana.perez@hospital-demo.example",
    "password": "ContraseñaSegura123",
    "acepta_tratamiento_datos": True,
}


def _log(pasos: list[dict], paso: str, detalle: str, **extra) -> None:
    print(f"        {detalle}")
    pasos.append({"paso": paso, "detalle": detalle, **extra})


def _pipeline_mockeado():
    """Mismos patches que tests/test_api.py: cero llamadas a un LLM real."""
    from backend.models.biomarkers import BiomarkerProfile
    from backend.models.case import ClinicalCase, PICOSynthesis
    from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
    from backend.models.report import AgentOutput, Report
    from backend.models.trial import TrialNavigationResult, TrialSearchSummary

    pico = PICOSynthesis(
        patient_profile="Varón, 42 años", chief_complaint="neuropatía axonal",
        relevant_history=[], negative_findings=[], disease_duration="2 años",
        current_treatments=[], procedures_done=[], comparison="No aplica",
        primary_outcome="identificar causa tratable", secondary_outcomes=[],
        biomarkers=[], genetic_findings=[], clinical_narrative="Caso de demo.",
    )
    case = ClinicalCase(raw_text="texto clínico de demo normalizado")
    case.pico = pico
    case.biomarkers = BiomarkerProfile()

    hyp = Hypothesis(
        text="Hipótesis de demo.", priority=Priority.HIGH, evidence_level=EvidenceLevel.II,
        sources=[Source(title="Fuente de demo", pmid="1")], rationale="Motivo de demo.",
    )
    report = Report(
        case_summary="Resumen de demo.", hypotheses=[hyp],
        agent_outputs=[AgentOutput(agent_id="01", agent_name="Analista de Literatura", hypotheses=[hyp])],
        sources_summary={"I": 0, "II": 1, "III": 0},
    )

    return (
        patch("backend.api.router.normalize", return_value="texto normalizado"),
        patch("backend.api.router.pico.build", return_value=case),
        patch("backend.api.router.extract_biomarkers", return_value=BiomarkerProfile()),
        patch("backend.api.router.orchestrator.run_round_1", new_callable=AsyncMock, return_value=report),
        patch("backend.api.router.debate.run_debate", new_callable=AsyncMock, return_value=report),
        patch(
            "backend.api.router.TrialNavigatorAgent.navigate",
            new_callable=AsyncMock,
            return_value=TrialNavigationResult(summary=TrialSearchSummary()),
        ),
        patch("backend.api.router.verify_report_sources", new_callable=AsyncMock, return_value={}),
        patch(
            "backend.api.router.ArbiterAgent.arbitrate",
            new_callable=AsyncMock,
            side_effect=RuntimeError("demo: sin llamada real a Groq"),
        ),
    )


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    pasos: list[dict] = []

    print(_SEP)
    print("  DEMO — Registro de médicos, revisión admin y pipeline protegido")
    print(_SEP)

    # ── 0. Base SQLite temporal, aislada de ./data/nexus.db ────────────────
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db_module.set_engine(engine)
    db_module.create_db_and_tables(bind=engine)
    print("\n  [0/8] Base SQLite temporal en memoria creada (no toca ./data/nexus.db).")

    client = TestClient(app, headers={"Origin": _ORIGIN})

    # ── 1. Registro de dos médicos ──────────────────────────────────────────
    print("\n  [1/8] Registrando dos médicos...")
    r_a = client.post("/api/registro", json=_MEDICO_A)
    r_b = client.post("/api/registro", json=_MEDICO_B)
    assert r_a.status_code == 201 and r_b.status_code == 201
    _log(pasos, "registro", f"Médico A ({_MEDICO_A['email']}) y B ({_MEDICO_B['email']}) registrados, ambos 'pendiente'.")

    # ── 2. A intenta analizar sin estar verificado ──────────────────────────
    print("\n  [2/8] A intenta analizar un caso sin estar verificado...")
    client_a = TestClient(app, headers={"Origin": _ORIGIN})
    login_a = client_a.post("/api/login", json={"email": _MEDICO_A["email"], "password": _MEDICO_A["password"]})
    assert login_a.status_code == 200
    intento = client_a.post("/api/analyze", data={"text": "caso clínico de demo"})
    assert intento.status_code == 403
    _log(pasos, "acceso_denegado", f"POST /api/analyze como médico 'pendiente' -> {intento.status_code} (esperado 403).")

    # ── 3. Alta del primer admin por CLI ────────────────────────────────────
    print("\n  [3/8] Alta del primer admin (backend.cli.crear_admin)...")
    admin = crear_admin("admin.demo@nexus.local", "ContraseñaAdmin123", engine_=engine)
    _log(pasos, "bootstrap_admin", f"Cuenta admin creada por CLI: {admin.email} (id={admin.id}).")

    client_admin = TestClient(app, headers={"Origin": _ORIGIN})
    login_admin = client_admin.post("/api/login", json={"email": admin.email, "password": "ContraseñaAdmin123"})
    assert login_admin.status_code == 200

    # ── 4. Admin lista pendientes y aprueba a B ─────────────────────────────
    print("\n  [4/8] Admin lista pendientes y aprueba a B...")
    pendientes = client_admin.get("/api/admin/pendientes").json()
    assert len(pendientes) == 2
    cuenta_b = next(c for c in pendientes if c["email"] == _MEDICO_B["email"])
    aprobacion = client_admin.post(
        f"/api/admin/cuentas/{cuenta_b['id']}/aprobar",
        json={"fuente_consultada": "Buscador Nacional REFEPS", "nota": "Coincide nombre, DNI y matrícula."},
    )
    assert aprobacion.status_code == 200 and aprobacion.json()["estado"] == "verificado"
    _log(pasos, "aprobacion", f"B aprobado (fuente: Buscador Nacional REFEPS) -> estado '{aprobacion.json()['estado']}'.")

    # ── 5. B analiza un caso (pipeline mockeado, cero LLM) ──────────────────
    print("\n  [5/8] B (ya verificado) analiza un caso clínico (pipeline mockeado)...")
    client_b = TestClient(app, headers={"Origin": _ORIGIN})
    login_b = client_b.post("/api/login", json={"email": _MEDICO_B["email"], "password": _MEDICO_B["password"]})
    assert login_b.status_code == 200
    patches = _pipeline_mockeado()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
        analisis = client_b.post("/api/analyze", data={"text": "caso clínico de demo"})
    assert analisis.status_code == 200
    _log(pasos, "analisis_permitido", f"POST /api/analyze como médico verificado -> {analisis.status_code}. Hipótesis: {len(analisis.json()['hypotheses'])}.")

    # ── 6. Admin rechaza a A con motivo ─────────────────────────────────────
    print("\n  [6/8] Admin rechaza a A con un motivo...")
    pendientes_2 = client_admin.get("/api/admin/pendientes").json()
    cuenta_a = next(c for c in pendientes_2 if c["email"] == _MEDICO_A["email"])
    motivo = "El nombre declarado no coincide con el que figura en el Buscador Nacional REFEPS."
    rechazo = client_admin.post(f"/api/admin/cuentas/{cuenta_a['id']}/rechazar", json={"motivo": motivo})
    assert rechazo.status_code == 200 and rechazo.json()["estado"] == "rechazado"
    _log(pasos, "rechazo", f"A rechazado -> estado '{rechazo.json()['estado']}', motivo: «{motivo}»")

    # ── 7. A ve el motivo y reenvía el registro corregido ───────────────────
    print("\n  [7/8] A ve el motivo y reenvía el registro corregido...")
    estado_a = client_a.get("/api/cuenta").json()
    assert estado_a["estado"] == "rechazado" and estado_a["motivo_rechazo"] == motivo
    corregido = dict(_MEDICO_A, nombre="Diego Ignacio")
    reenvio = client_a.put("/api/registro", json=corregido)
    assert reenvio.status_code == 200 and reenvio.json()["estado"] == "pendiente"
    _log(pasos, "reenvio", f"A corrigió su nombre y reenvió -> estado '{reenvio.json()['estado']}' (motivo limpiado: {reenvio.json()['motivo_rechazo']}).")

    # ── 8. Auditoría: exactamente dos decisiones registradas ───────────────
    print("\n  [8/8] Verificando el registro de auditoría...")
    from sqlmodel import Session, select

    from backend.models.auditoria import DecisionAuditoria

    with Session(engine) as session:
        auditoria = session.exec(select(DecisionAuditoria)).all()
    assert len(auditoria) == 2
    auditoria_out = [
        {"admin_id": a.admin_id, "cuenta_id": a.cuenta_id, "decision": a.decision.value,
         "motivo": a.motivo, "fuente_consultada": a.fuente_consultada}
        for a in auditoria
    ]
    _log(pasos, "auditoria", f"{len(auditoria)} registros de auditoría (uno por decisión), sin excepciones.")

    # ── Artefactos ───────────────────────────────────────────────────────────
    flujo = {
        "medico_a_final": client_a.get("/api/cuenta").json(),
        "medico_b_final": client_b.get("/api/cuenta").json(),
        "auditoria": auditoria_out,
        "pasos": pasos,
    }
    (_OUT_DIR / "flujo.json").write_text(
        json.dumps(flujo, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    with (_OUT_DIR / "resumen.txt").open("w", encoding="utf-8") as f:
        f.write("NEXUS — Demo: registro de médicos, revisión admin y pipeline protegido\n")
        f.write("=" * 72 + "\n\n")
        for i, p in enumerate(pasos, 1):
            f.write(f"{i}. [{p['paso']}] {p['detalle']}\n")
        f.write("\nAuditoría:\n")
        for a in auditoria_out:
            f.write(f"  - {a}\n")

    print(f"\n{_SEP}")
    print(f"  Artefactos en {_OUT_DIR}")
    print(_SEP)


if __name__ == "__main__":
    main()
