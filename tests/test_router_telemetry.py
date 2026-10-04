"""
Tests de la integración de la telemetría de costos en el router
(backend/api/router.py — control de costos, Sprint 4).

Cubre que `POST /api/analyze` abre un registro al empezar el análisis y lo
cierra siempre al terminar (D2), incluso si el pipeline falla a mitad de
camino, y que el registro de un análisis real no contiene texto clínico
(task 2.7). El pipeline está mockeado con el mismo criterio que
`tests/test_api.py`: no se llama a ningún LLM ni a ninguna API externa.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.models.biomarkers import BiomarkerProfile
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import AgentOutput, Report
from backend.models.trial import TrialNavigationResult, TrialSearchSummary
from backend.telemetry import usage

CASO_CLINICO = (
    "Paciente masculino de 42 años con neuropatía axonal sensitivomotora "
    "progresiva, panel CMT negativo, anticuerpos anti-Hu anti-Yo anti-Ri negativos."
)


def _pico() -> PICOSynthesis:
    return PICOSynthesis(
        patient_profile="Varón, 42 años",
        chief_complaint="neuropatía axonal sensitivomotora",
        relevant_history=[], negative_findings=[], disease_duration="2 años",
        current_treatments=[], procedures_done=["EMG"], comparison="No aplica",
        primary_outcome="identificar causa tratable", secondary_outcomes=[],
        biomarkers=[], genetic_findings=[],
        clinical_narrative=CASO_CLINICO,
    )


def _case_con_pico() -> ClinicalCase:
    case = ClinicalCase(raw_text=CASO_CLINICO)
    case.pico = _pico()
    case.biomarkers = BiomarkerProfile(genes=["TTR"])
    return case


def _report() -> Report:
    hipotesis = Hypothesis(
        text="Neuropatía axonal por deficiencia de vitamina B12.",
        priority=Priority.HIGH, evidence_level=EvidenceLevel.II,
        sources=[Source(title="Estudio B12 y neuropatía", pmid="12345678")],
        rationale="Hallazgos compatibles con déficit de vitamina B12.",
    )
    return Report(
        case_summary=CASO_CLINICO, hypotheses=[hipotesis],
        agent_outputs=[AgentOutput(agent_id="01", agent_name="Analista de Literatura",
                                    hypotheses=[hipotesis])],
        sources_summary={"I": 0, "II": 1, "III": 0},
    )


def _patches():
    return {
        "normalize": patch("backend.api.router.normalize", return_value="texto normalizado"),
        "pico_build": patch("backend.api.router.pico.build", return_value=_case_con_pico()),
        "extract_biomarkers": patch(
            "backend.api.router.extract_biomarkers", return_value=BiomarkerProfile(genes=["TTR"]),
        ),
        "run_round_1": patch(
            "backend.api.router.orchestrator.run_round_1",
            new_callable=AsyncMock, return_value=_report(),
        ),
        "run_debate": patch(
            "backend.api.router.debate.run_debate",
            new_callable=AsyncMock, return_value=_report(),
        ),
        "verify": patch(
            "backend.api.router.verify_report_sources",
            new_callable=AsyncMock, return_value={},
        ),
        "navigate": patch(
            "backend.api.router.TrialNavigatorAgent.navigate",
            new_callable=AsyncMock,
            return_value=TrialNavigationResult(summary=TrialSearchSummary(
                estado_clinicaltrials="ok", estado_orphanet="ok",
            )),
        ),
    }


def _run_analisis(client, **kwargs):
    patches = _patches()
    with (
        patches["normalize"], patches["pico_build"], patches["extract_biomarkers"],
        patches["run_round_1"], patches["run_debate"], patches["verify"],
        patches["navigate"],
        patch(
            "backend.api.router._arbitrate_safe",
            new_callable=AsyncMock,
            return_value=_arbitration_result_vacio(),
        ),
    ):
        return client.post("/api/analyze", data=kwargs.get("data", {"text": CASO_CLINICO}))


def _arbitration_result_vacio():
    from backend.models.arbitration import ArbitrationResult, ArbitrationSummary

    return ArbitrationResult(consensus=[], summary=ArbitrationSummary())


# ── El router abre y cierra un registro por análisis (D2) ────────────────────────

class TestAperturaYCierreDelRegistro:
    def test_abre_y_cierra_un_registro(self, client_medico_verificado_sin_relanzar):
        with patch(
            "backend.api.router.usage_telemetry.open_registry",
            return_value="token-de-prueba",
        ) as abrir, patch(
            "backend.api.router.usage_telemetry.close_registry",
        ) as cerrar:
            response = _run_analisis(client_medico_verificado_sin_relanzar)

        assert response.status_code == 200
        abrir.assert_called_once()
        cerrar.assert_called_once()
        assert cerrar.call_args.args[0] == "token-de-prueba"

    def test_cierra_el_registro_aunque_el_pipeline_falle(
        self, client_medico_verificado_sin_relanzar
    ):
        patches = _patches()
        patches["run_round_1"] = patch(
            "backend.api.router.orchestrator.run_round_1",
            new_callable=AsyncMock, side_effect=RuntimeError("falla simulada del pipeline"),
        )
        with (
            patches["normalize"], patches["pico_build"], patches["extract_biomarkers"],
            patches["run_round_1"],
            patch(
                "backend.api.router.usage_telemetry.open_registry",
                return_value="token-de-prueba",
            ) as abrir,
            patch("backend.api.router.usage_telemetry.close_registry") as cerrar,
        ):
            client_medico_verificado_sin_relanzar.post(
                "/api/analyze", data={"text": CASO_CLINICO}
            )

        abrir.assert_called_once()
        cerrar.assert_called_once()
        assert cerrar.call_args.args[0] == "token-de-prueba"

    def test_no_abre_registro_si_falta_el_texto_y_el_archivo(self, client_medico_verificado):
        """El 422 de entrada inválida es previo a cualquier análisis."""
        with patch("backend.api.router.usage_telemetry.open_registry") as abrir:
            response = client_medico_verificado.post("/api/analyze")
        assert response.status_code == 422
        abrir.assert_not_called()


# ── Privacidad: el registro de un análisis real no contiene texto clínico ───────

class TestPrivacidadDelRegistroEnUnAnalisisReal:
    def test_el_registro_no_contiene_el_texto_clinico(
        self, tmp_path, monkeypatch, client_medico_verificado_sin_relanzar
    ):
        """
        Task 2.7. Corre un análisis (con el LLM y las APIs externas
        mockeadas, como el resto de esta suite) y verifica que el resumen de
        telemetría que produce el router no contiene ninguna palabra del caso.
        """
        destino = tmp_path / "costos.jsonl"
        monkeypatch.setattr(usage, "_DEFAULT_OUTPUT_PATH", destino)

        response = _run_analisis(client_medico_verificado_sin_relanzar)
        assert response.status_code == 200

        if destino.exists():
            contenido = destino.read_text(encoding="utf-8")
            assert CASO_CLINICO not in contenido
            assert "neuropatía" not in contenido.lower()
            assert "anti-hu" not in contenido.lower()
