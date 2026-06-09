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
from backend.models.trial import ClinicalTrial


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
        "search_by_biomarkers": patch(
            "backend.api.router.search_by_biomarkers",
            return_value=[_make_trial()],
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
            patches["search_by_biomarkers"],
            TestClient(app) as client,
        ):
            return client.post("/api/analyze", **request_kwargs)

    def test_texto_plano_devuelve_200(self):
        response = self._run(data={"text": "Paciente masculino 42 años con neuropatía."})
        assert response.status_code == 200

    def test_respuesta_incluye_report_y_trials(self):
        response = self._run(data={"text": "caso clínico de prueba"})
        body = response.json()
        assert "report" in body
        assert "trials" in body
        assert "processing_time_seconds" in body

    def test_report_tiene_hipotesis(self):
        response = self._run(data={"text": "caso clínico de prueba"})
        hypotheses = response.json()["report"]["hypotheses"]
        assert len(hypotheses) > 0
        assert "text" in hypotheses[0]
        assert "evidence_level" in hypotheses[0]

    def test_trials_son_lista(self):
        response = self._run(data={"text": "caso clínico de prueba"})
        trials = response.json()["trials"]
        assert isinstance(trials, list)
        assert trials[0]["nct_id"] == "NCT04000001"

    def test_processing_time_es_numero(self):
        response = self._run(data={"text": "caso clínico de prueba"})
        assert isinstance(response.json()["processing_time_seconds"], float)

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

    def test_fallo_en_trials_no_rompe_el_pipeline(self):
        patches = _pipeline_patches()
        patches["search_by_biomarkers"] = patch(
            "backend.api.router.search_by_biomarkers",
            side_effect=RuntimeError("API no disponible"),
        )
        with (
            patches["normalize"],
            patches["pico_build"],
            patches["extract_biomarkers"],
            patches["run_round_1"],
            patches["run_debate"],
            patches["search_by_biomarkers"],
            TestClient(app) as client,
        ):
            response = client.post("/api/analyze", data={"text": "caso clínico"})
        assert response.status_code == 200
        assert response.json()["trials"] == []

    def test_llama_a_run_round_1_con_case(self):
        patches = _pipeline_patches()
        with (
            patches["normalize"],
            patches["pico_build"],
            patches["extract_biomarkers"],
            patches["run_round_1"] as mock_round_1,
            patches["run_debate"],
            patches["search_by_biomarkers"],
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
            patches["search_by_biomarkers"],
            TestClient(app) as client,
        ):
            client.post("/api/analyze", data={"text": "texto clínico"})
        mock_debate.assert_awaited_once()

    def test_biomarkers_vacios_no_rompen_busqueda_trials(self):
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
            patches["search_by_biomarkers"],
            TestClient(app) as client,
        ):
            response = client.post("/api/analyze", data={"text": "texto clínico"})
        assert response.status_code == 200
