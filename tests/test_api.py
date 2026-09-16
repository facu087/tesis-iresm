"""
Tests del endpoint POST /api/analyze y GET /health.
Todos los tests mockean el pipeline — no realizan llamadas reales a LLMs ni APIs externas.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.biomarkers import BiomarkerProfile
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import AgentOutput, Report
from backend.models.trial import (
    ClinicalTrial,
    RareDiseaseMatch,
    TrialNavigationResult,
    TrialSearchSummary,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_pico() -> PICOSynthesis:
    return PICOSynthesis(
        patient_profile="Varón, 42 años",
        chief_complaint="neuropatía axonal sensitivomotora",
        relevant_history=["diabetes tipo 2"],
        negative_findings=[],
        disease_duration="2 años",
        current_treatments=["pregabalina"],
        procedures_done=["EMG"],
        comparison="No aplica",
        primary_outcome="identificar causa tratable",
        secondary_outcomes=[],
        biomarkers=[],
        genetic_findings=[],
        clinical_narrative="Paciente varón de 42 años con neuropatía axonal de evolución lenta.",
    )


def _make_hypothesis() -> Hypothesis:
    return Hypothesis(
        text="Neuropatía axonal por deficiencia de vitamina B12.",
        priority=Priority.HIGH,
        evidence_level=EvidenceLevel.II,
        sources=[Source(title="Estudio B12 y neuropatía", pmid="12345678")],
        rationale="Hallazgos compatibles con déficit de vitamina B12.",
    )


def _make_report() -> Report:
    output = AgentOutput(
        agent_id="01",
        agent_name="Analista de Literatura",
        hypotheses=[_make_hypothesis()],
    )
    return Report(
        case_summary="Varón 42 años, neuropatía axonal sensitivomotora.",
        hypotheses=[_make_hypothesis()],
        agent_outputs=[output],
        sources_summary={"I": 0, "II": 1, "III": 0},
    )


def _make_case_with_pico() -> ClinicalCase:
    case = ClinicalCase(raw_text="texto clínico de prueba normalizado")
    case.pico = _make_pico()
    case.biomarkers = BiomarkerProfile(genes=["TTR"], drugs=["pregabalina"])
    return case


def _make_trial() -> ClinicalTrial:
    return ClinicalTrial(
        nct_id="NCT04000001",
        title="Estudio de neuropatía axonal hereditaria",
        status="RECRUITING",
        brief_summary="Ensayo sobre tratamiento de neuropatía.",
        conditions=["Axonal Neuropathy"],
        phase="PHASE3",
        locations=["Argentina"],
        url="https://clinicaltrials.gov/study/NCT04000001",
        compatibility="alta",
        compatibility_rationale="Coincide con la condición estudiada.",
        criteria_to_verify=["Confirmar biopsia de nervio"],
        related_hypotheses=["Neuropatía axonal por deficiencia de vitamina B12."],
        matched_terms=["axonal sensorimotor polyneuropathy"],
    )


def _make_navigation() -> TrialNavigationResult:
    """Resultado típico del Agente 05 con ambas APIs respondiendo."""
    return TrialNavigationResult(
        trials=[_make_trial()],
        rare_diseases=[
            RareDiseaseMatch(
                orpha_code="271861",
                name="Hereditary ATTR amyloidosis",
                url="https://www.orpha.net/en/disease/detail/271861",
                hypothesis="Neuropatía axonal por deficiencia de vitamina B12.",
                matched_term="hereditary ATTR amyloidosis",
            )
        ],
        summary=TrialSearchSummary(
            estado_clinicaltrials="ok",
            estado_orphanet="ok",
            planificacion="ok",
            evaluacion="ok",
            terminos_consultados=["axonal sensorimotor polyneuropathy"],
            encontrados=1,
        ),
    )


# ── Contexto de mocks completo ─────────────────────────────────────────────────

def _pipeline_patches():
    """Devuelve un dict con todos los patches necesarios para el pipeline."""
    return {
        "normalize": patch(
            "backend.api.router.normalize",
            return_value="texto normalizado",
        ),
        "pico_build": patch(
            "backend.api.router.pico.build",
            return_value=_make_case_with_pico(),
        ),
        "extract_biomarkers": patch(
            "backend.api.router.extract_biomarkers",
            return_value=BiomarkerProfile(genes=["TTR"]),
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
        # Paso 6: el Agente 05 reemplazó a search_by_biomarkers en el router.
        "navigate": patch(
            "backend.api.router.TrialNavigatorAgent.navigate",
            new_callable=AsyncMock,
            return_value=_make_navigation(),
        ),
    }


# ── Tests: /health ─────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_devuelve_ok(self):
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["service"] == "NEXUS"

    def test_health_incluye_version(self):
        with TestClient(app) as client:
            response = client.get("/health")
        assert "version" in response.json()


# ── Tests: POST /api/analyze ───────────────────────────────────────────────────

class TestAnalyzeEndpoint:
    def _run(self, **request_kwargs):
        """Lanza la request con todos los mocks activos."""
        patches = _pipeline_patches()
        with (
            patches["normalize"],
            patches["pico_build"],
            patches["extract_biomarkers"],
            patches["run_round_1"],
            patches["run_debate"],
            patches["navigate"],
            TestClient(app) as client,
        ):
            return client.post("/api/analyze", **request_kwargs)

    def test_texto_plano_devuelve_200(self):
        response = self._run(data={"text": "Paciente masculino 42 años con neuropatía."})
        assert response.status_code == 200

    def test_respuesta_incluye_secciones_del_reporte(self):
        response = self._run(data={"text": "caso clínico de prueba"})
        body = response.json()
        assert "metadata" in body
        assert "case_summary" in body
        assert "hypotheses" in body
        assert "debate_summary" in body
        assert "clinical_trials" in body
        assert "bibliography" in body

    def test_report_tiene_hipotesis(self):
        response = self._run(data={"text": "caso clínico de prueba"})
        hypotheses = response.json()["hypotheses"]
        assert len(hypotheses) > 0
        assert "text" in hypotheses[0]
        assert "evidence_level" in hypotheses[0]
        assert "rank" in hypotheses[0]

    def test_trials_son_lista(self):
        response = self._run(data={"text": "caso clínico de prueba"})
        trials = response.json()["clinical_trials"]
        assert isinstance(trials, list)
        assert trials[0]["nct_id"] == "NCT04000001"

    def test_processing_time_es_numero(self):
        response = self._run(data={"text": "caso clínico de prueba"})
        assert isinstance(response.json()["metadata"]["processing_time_seconds"], float)

    def test_sin_parametros_devuelve_422(self):
        with TestClient(app) as client:
            response = client.post("/api/analyze")
        assert response.status_code == 422

    def test_texto_vacio_devuelve_422(self):
        response = self._run(data={"text": "   "})
        assert response.status_code == 422

    def test_archivo_pdf_es_procesado(self):
        pdf_bytes = b"%PDF-1.4 fake pdf content for testing"
        with patch("backend.api.router.extract", return_value="texto extraído del PDF"):
            response = self._run(
                files={"file": ("informe.pdf", pdf_bytes, "application/pdf")},
            )
        assert response.status_code == 200

    def test_archivo_vacio_devuelve_422(self):
        with TestClient(app) as client:
            response = client.post(
                "/api/analyze",
                files={"file": ("vacio.pdf", b"", "application/pdf")},
            )
        assert response.status_code == 422

    def test_formato_no_soportado_devuelve_415(self):
        with patch(
            "backend.api.router.extract",
            side_effect=ValueError("Formato no soportado: .docx. Formatos válidos: pdf, txt."),
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/api/analyze",
                    files={"file": ("doc.docx", b"contenido", "application/octet-stream")},
                )
        assert response.status_code == 415

    def test_error_inesperado_dentro_del_agente_no_rompe_el_pipeline(self):
        """El router tiene su propia red de seguridad sobre el Agente 05."""
        patches = _pipeline_patches()
        patches["navigate"] = patch(
            "backend.api.router.TrialNavigatorAgent.navigate",
            new_callable=AsyncMock,
            side_effect=RuntimeError("error no previsto"),
        )
        with (
            patches["normalize"],
            patches["pico_build"],
            patches["extract_biomarkers"],
            patches["run_round_1"],
            patches["run_debate"],
            patches["navigate"],
            TestClient(app) as client,
        ):
            response = client.post("/api/analyze", data={"text": "caso clínico"})
        body = response.json()
        assert response.status_code == 200
        assert body["clinical_trials"] == []
        assert body["trial_search"]["estado_clinicaltrials"] == "no_disponible"

    def test_respuesta_incluye_compatibilidad_y_estado_de_la_busqueda(self):
        response = self._run(data={"text": "caso clínico de prueba"})
        body = response.json()
        assert body["clinical_trials"][0]["compatibility"] == "alta"
        assert body["clinical_trials"][0]["criteria_to_verify"]
        assert body["trial_search"]["estado_orphanet"] == "ok"
        assert body["rare_diseases"][0]["orpha_code"] == "271861"

    def test_el_agente_recibe_las_hipotesis_del_debate(self):
        patches = _pipeline_patches()
        with (
            patches["normalize"],
            patches["pico_build"],
            patches["extract_biomarkers"],
            patches["run_round_1"],
            patches["run_debate"],
            patches["navigate"] as mock_navigate,
            TestClient(app) as client,
        ):
            client.post("/api/analyze", data={"text": "texto clínico"})
        entrada = mock_navigate.await_args.args[0]
        assert [c.text for c in entrada.candidates] == [
            "Neuropatía axonal por deficiencia de vitamina B12."
        ]
        # El motivo de consulta en español no se usa como condición de reemplazo.
        assert entrada.condition_en == ""

    def test_llama_a_run_round_1_con_case(self):
        patches = _pipeline_patches()
        with (
            patches["normalize"],
            patches["pico_build"],
            patches["extract_biomarkers"],
            patches["run_round_1"] as mock_round_1,
            patches["run_debate"],
            patches["navigate"],
            TestClient(app) as client,
        ):
            client.post("/api/analyze", data={"text": "texto clínico"})
        mock_round_1.assert_awaited_once()

    def test_llama_a_run_debate_con_report_de_ronda_1(self):
        patches = _pipeline_patches()
        with (
            patches["normalize"],
            patches["pico_build"],
            patches["extract_biomarkers"],
            patches["run_round_1"],
            patches["run_debate"] as mock_debate,
            patches["navigate"],
            TestClient(app) as client,
        ):
            client.post("/api/analyze", data={"text": "texto clínico"})
        mock_debate.assert_awaited_once()

    def test_biomarkers_vacios_no_rompen_busqueda(self):
        patches = _pipeline_patches()
        patches["extract_biomarkers"] = patch(
            "backend.api.router.extract_biomarkers",
            return_value=BiomarkerProfile(),  # perfil vacío
        )
        with (
            patches["normalize"],
            patches["pico_build"],
            patches["extract_biomarkers"],
            patches["run_round_1"],
            patches["run_debate"],
            patches["navigate"],
            TestClient(app) as client,
        ):
            response = client.post("/api/analyze", data={"text": "texto clínico"})
        assert response.status_code == 200


# ── Tests: POST /api/report/pdf ────────────────────────────────────────────────

def _reporte_previo() -> dict:
    """
    JSON tal como lo generaba NEXUS antes del Agente 05.

    Sin `trial_search`, sin `rare_diseases` y con ensayos sin `compatibility`:
    el contrato nuevo es aditivo, así que tiene que seguir siendo aceptado.
    """
    return {
        "metadata": {
            "generated_at": "2026-06-09T12:00:00Z",
            "nexus_version": "0.3.0",
            "processing_time_seconds": 42.5,
            "disclaimer": "NEXUS es un sistema de soporte investigativo.",
        },
        "case_summary": {"narrative": "Paciente varón de 42 años."},
        "hypotheses": [],
        "debate_summary": {
            "rounds_completed": 4,
            "total_critiques": 3,
            "divergences": [],
            "consensus_reached": True,
        },
        "clinical_trials": [
            {
                "nct_id": "NCT04000001",
                "title": "Estudio de neuropatía axonal hereditaria",
                "status": "RECRUITING",
                "brief_summary": "Ensayo sobre tratamiento.",
                "conditions": ["Axonal Neuropathy"],
                "locations": ["Argentina"],
                "url": "https://clinicaltrials.gov/study/NCT04000001",
            }
        ],
        "bibliography": [],
    }


class TestExportPdfEndpoint:
    def test_reporte_previo_sin_campos_nuevos_devuelve_200(self):
        with TestClient(app) as client:
            response = client.post("/api/report/pdf", json=_reporte_previo())
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

    def test_reporte_previo_queda_sin_evaluar(self):
        """El ensayo del reporte viejo toma el default del contrato nuevo."""
        from backend.api.schemas import StructuredReport

        reporte = StructuredReport(**_reporte_previo())
        assert reporte.trial_search is None
        assert reporte.rare_diseases == []
        assert reporte.clinical_trials[0].compatibility == "sin_evaluar"
