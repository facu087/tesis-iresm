"""
Tests del exportador PDF (backend/pipeline/pdf_exporter.py).
Verifica que generate_pdf() produzca un PDF válido con el contenido esperado.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.schemas import (
    CaseSummarySection,
    DebateSummary,
    RankedHypothesis,
    ReportMetadata,
    StructuredReport,
)
from backend.main import app
from backend.models.hypothesis import Source
from backend.models.trial import ClinicalTrial
from backend.pipeline.pdf_exporter import generate_pdf


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_report(
    hypotheses: list[RankedHypothesis] | None = None,
    trials: list[ClinicalTrial] | None = None,
    bibliography: list[Source] | None = None,
    divergences: list[str] | None = None,
) -> StructuredReport:
    return StructuredReport(
        metadata=ReportMetadata(
            generated_at=datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc),
            nexus_version="0.3.0",
            processing_time_seconds=42.5,
        ),
        case_summary=CaseSummarySection(
            narrative="Paciente varón de 42 años con neuropatía axonal sensitivomotora.",
            patient_profile="Varón, 42 años",
            chief_complaint="neuropatía axonal",
            disease_duration="2 años",
            current_treatments=["pregabalina"],
            relevant_history=["diabetes tipo 2"],
            procedures_done=["EMG", "biopsia de nervio"],
        ),
        hypotheses=hypotheses or [
            RankedHypothesis(
                rank=1,
                text="Neuropatía axonal por deficiencia de vitamina B12.",
                priority="HIGH",
                evidence_level="II",
                rationale="Hallazgos compatibles con déficit.",
                supporting_agents=["Analista de Literatura", "Consultor Clínico"],
                sources=[Source(pmid="12345678", title="Estudio B12", year=2022)],
            ),
            RankedHypothesis(
                rank=2,
                text="Neuropatía axonal de origen paraneoplásico.",
                priority="MEDIUM",
                evidence_level="III",
                rationale="Descartar origen oncológico.",
                supporting_agents=["Consultor Clínico"],
                sources=[],
            ),
        ],
        debate_summary=DebateSummary(
            rounds_completed=4,
            total_critiques=3,
            divergences=divergences or [],
            consensus_reached=True,
        ),
        clinical_trials=trials or [
            ClinicalTrial(
                nct_id="NCT04000001",
                title="Estudio de neuropatía axonal hereditaria",
                status="RECRUITING",
                brief_summary="Ensayo sobre tratamiento.",
                conditions=["Axonal Neuropathy"],
                phase="PHASE3",
                locations=["Argentina", "Brazil"],
                min_age="18 Years",
                max_age="70 Years",
                url="https://clinicaltrials.gov/study/NCT04000001",
            )
        ],
        bibliography=bibliography or [
            Source(pmid="12345678", title="Estudio B12 y neuropatía", journal="NEJM", year=2022),
        ],
    )


# ── Tests: generate_pdf ────────────────────────────────────────────────────────

class TestGeneratePdf:
    def test_devuelve_bytes(self):
        result = generate_pdf(_make_report())
        assert isinstance(result, bytes)

    def test_es_pdf_valido(self):
        result = generate_pdf(_make_report())
        assert result[:4] == b"%PDF"

    def test_pdf_no_vacio(self):
        result = generate_pdf(_make_report())
        assert len(result) > 1024  # al menos 1 KB

    def test_sin_hipotesis(self):
        result = generate_pdf(_make_report(hypotheses=[]))
        assert result[:4] == b"%PDF"

    def test_sin_trials(self):
        result = generate_pdf(_make_report(trials=[]))
        assert result[:4] == b"%PDF"

    def test_sin_bibliografia(self):
        result = generate_pdf(_make_report(bibliography=[]))
        assert result[:4] == b"%PDF"

    def test_con_divergencias(self):
        result = generate_pdf(_make_report(
            divergences=["Agente 01 mantuvo hipótesis criticada [HIGH] por Agente 03."]
        ))
        assert result[:4] == b"%PDF"

    def test_caso_sin_pico(self):
        report = _make_report()
        report.case_summary = CaseSummarySection(
            narrative="Narrativa básica sin campos PICO.",
        )
        result = generate_pdf(report)
        assert result[:4] == b"%PDF"

    def test_hipotesis_con_muchas_fuentes(self):
        h = RankedHypothesis(
            rank=1,
            text="Hipótesis con muchas fuentes.",
            priority="HIGH",
            evidence_level="I",
            rationale="Bien respaldada.",
            supporting_agents=[],
            sources=[
                Source(pmid=f"{i:08d}", title=f"Estudio {i}", year=2020 + i)
                for i in range(10)
            ],
        )
        result = generate_pdf(_make_report(hypotheses=[h]))
        assert result[:4] == b"%PDF"

    def test_texto_largo_no_falla(self):
        h = RankedHypothesis(
            rank=1,
            text="X " * 500,
            priority="LOW",
            evidence_level="III",
            rationale="Razonamiento " * 100,
            supporting_agents=["Agente 01"],
            sources=[],
        )
        result = generate_pdf(_make_report(hypotheses=[h]))
        assert result[:4] == b"%PDF"

    def test_caracteres_espanoles(self):
        report = _make_report()
        report.case_summary.narrative = (
            "Paciente con neuropatía periférica, pérdida de sensación y "
            "déficit motor en miembros inferiores. Síntomas de evolución lenta."
        )
        result = generate_pdf(report)
        assert result[:4] == b"%PDF"


# ── Tests: endpoint /api/report/pdf ───────────────────────────────────────────

class TestExportPdfEndpoint:
    def _report_json(self) -> dict:
        return _make_report().model_dump(mode="json")

    def test_endpoint_devuelve_200(self):
        with TestClient(app) as client:
            response = client.post("/api/report/pdf", json=self._report_json())
        assert response.status_code == 200

    def test_content_type_es_pdf(self):
        with TestClient(app) as client:
            response = client.post("/api/report/pdf", json=self._report_json())
        assert response.headers["content-type"] == "application/pdf"

    def test_content_disposition_tiene_filename(self):
        with TestClient(app) as client:
            response = client.post("/api/report/pdf", json=self._report_json())
        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "nexus_reporte" in cd
        assert ".pdf" in cd

    def test_body_es_pdf_valido(self):
        with TestClient(app) as client:
            response = client.post("/api/report/pdf", json=self._report_json())
        assert response.content[:4] == b"%PDF"

    def test_body_invalido_devuelve_422(self):
        with TestClient(app) as client:
            response = client.post("/api/report/pdf", json={"invalid": "data"})
        assert response.status_code == 422
