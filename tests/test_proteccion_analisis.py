"""
Tests de la protección de `POST /api/analyze` y `POST /api/report/pdf`
(sección 6 de tasks.md, spec `proteccion-analisis-clinico`).

Todos mockean el pipeline (nunca llaman a un LLM real) — igual que
`tests/test_api.py`. Se ejercitan las respuestas de autorización (401/403)
sin necesidad de mockear nada, porque el gate corta antes de tocar el
pipeline; el caso 200 sí monta los mocks completos, igual que
`tests/test_api.py::_pipeline_patches`.
"""

from unittest.mock import AsyncMock, patch

from backend.models.biomarkers import BiomarkerProfile
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import AgentOutput, Report
from backend.models.trial import TrialNavigationResult, TrialSearchSummary


def _make_pico() -> PICOSynthesis:
    return PICOSynthesis(
        patient_profile="Varón, 42 años",
        chief_complaint="neuropatía axonal sensitivomotora",
        relevant_history=[],
        negative_findings=[],
        disease_duration="2 años",
        current_treatments=[],
        procedures_done=[],
        comparison="No aplica",
        primary_outcome="identificar causa tratable",
        secondary_outcomes=[],
        biomarkers=[],
        genetic_findings=[],
        clinical_narrative="Paciente de prueba.",
    )


def _make_case_with_pico() -> ClinicalCase:
    case = ClinicalCase(raw_text="texto clínico de prueba normalizado")
    case.pico = _make_pico()
    case.biomarkers = BiomarkerProfile()
    return case


def _make_report() -> Report:
    hyp = Hypothesis(
        text="Hipótesis de prueba.",
        priority=Priority.HIGH,
        evidence_level=EvidenceLevel.II,
        sources=[Source(title="Fuente de prueba", pmid="1")],
        rationale="Motivo de prueba.",
    )
    output = AgentOutput(agent_id="01", agent_name="Analista de Literatura", hypotheses=[hyp])
    return Report(
        case_summary="Resumen de prueba.",
        hypotheses=[hyp],
        agent_outputs=[output],
        sources_summary={"I": 0, "II": 1, "III": 0},
    )


def _pipeline_patches():
    return {
        "normalize": patch("backend.api.router.normalize", return_value="texto normalizado"),
        "pico_build": patch("backend.api.router.pico.build", return_value=_make_case_with_pico()),
        "extract_biomarkers": patch(
            "backend.api.router.extract_biomarkers", return_value=BiomarkerProfile()
        ),
        "run_round_1": patch(
            "backend.api.router.orchestrator.run_round_1",
            new_callable=AsyncMock,
            return_value=_make_report(),
        ),
        "run_debate": patch(
            "backend.api.router.debate.run_debate",
            new_callable=AsyncMock,
            return_value=_make_report(),
        ),
        "navigate": patch(
            "backend.api.router.TrialNavigatorAgent.navigate",
            new_callable=AsyncMock,
            return_value=TrialNavigationResult(summary=TrialSearchSummary()),
        ),
    }


def _con_pipeline_mockeado(client, **request_kwargs):
    patches = _pipeline_patches()
    with (
        patches["normalize"],
        patches["pico_build"],
        patches["extract_biomarkers"],
        patches["run_round_1"],
        patches["run_debate"],
        patches["navigate"],
    ):
        return client.post("/api/analyze", **request_kwargs)


class TestSesionObligatoriaParaAnalizar:
    def test_sin_sesion_devuelve_401_sin_ejecutar_el_pipeline(self, client):
        with patch("backend.api.router.orchestrator.run_round_1") as mock_round_1:
            resp = client.post("/api/analyze", data={"text": "caso clínico"})
        assert resp.status_code == 401
        mock_round_1.assert_not_called()


class TestSoloMedicosVerificadosPuedenAnalizar:
    def test_medico_pendiente_recibe_403(self, client, cuenta_medico_pendiente):
        client.post(
            "/api/login",
            json={"email": cuenta_medico_pendiente.email, "password": "ContraseñaSegura123"},
        )
        with patch("backend.api.router.orchestrator.run_round_1") as mock_round_1:
            resp = client.post("/api/analyze", data={"text": "caso clínico"})
        assert resp.status_code == 403
        mock_round_1.assert_not_called()

    def test_medico_rechazado_recibe_403(self, client, _base_de_datos_temporal):
        from backend.auth.security import hash_password
        from backend.models.cuenta import CuentaMedico, EstadoCuenta, RolCuenta
        from sqlmodel import Session

        with Session(_base_de_datos_temporal) as session:
            cuenta = CuentaMedico(
                nombre="R",
                apellido="R",
                dni="1",
                matricula="2",
                jurisdiccion="CABA",
                email="rechazado.analiza@hospital.example",
                password_hash=hash_password("ContraseñaSegura123"),
                rol=RolCuenta.MEDICO,
                estado=EstadoCuenta.RECHAZADO,
                motivo_rechazo="x",
            )
            session.add(cuenta)
            session.commit()
        client.post(
            "/api/login",
            json={"email": "rechazado.analiza@hospital.example", "password": "ContraseñaSegura123"},
        )
        resp = client.post("/api/analyze", data={"text": "caso clínico"})
        assert resp.status_code == 403

    def test_admin_sin_cuenta_medico_verificada_recibe_403(self, client_admin):
        resp = client_admin.post("/api/analyze", data={"text": "caso clínico"})
        assert resp.status_code == 403

    def test_medico_verificado_puede_analizar(self, client_medico_verificado):
        resp = _con_pipeline_mockeado(client_medico_verificado, data={"text": "caso clínico"})
        assert resp.status_code == 200


class TestExportacionPdfExigeSesion:
    def test_sin_sesion_devuelve_401(self, client):
        resp = client.post("/api/report/pdf", json={})
        assert resp.status_code == 401


class TestValidacionDeOrigenEnAnalisisYExportacion:
    def test_multipart_con_origen_ajeno_y_sesion_valida_rechaza_sin_ejecutar_pipeline(
        self, client_medico_verificado
    ):
        with patch("backend.api.router.orchestrator.run_round_1") as mock_round_1:
            resp = client_medico_verificado.post(
                "/api/analyze",
                data={"text": "caso clínico"},
                headers={"Origin": "https://sitio-ajeno.example"},
            )
        assert resp.status_code == 403
        mock_round_1.assert_not_called()

    def test_origen_permitido_continua_a_verificaciones_normales(self, client_medico_verificado):
        resp = _con_pipeline_mockeado(
            client_medico_verificado,
            data={"text": "caso clínico"},
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 200

    def test_pdf_con_origen_ajeno_rechaza(self, client_medico_verificado):
        resp = client_medico_verificado.post(
            "/api/report/pdf", json={}, headers={"Origin": "https://sitio-ajeno.example"}
        )
        assert resp.status_code == 403
