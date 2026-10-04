"""
Tests del modo mock del pipeline (control de costos, Sprint 4 — D7).

Cubre: activación explícita por variable de entorno y apagada por defecto
(task 6.3), que las respuestas grabadas atraviesan el parseo y las
validaciones reales de cada sitio de llamada (6.1), determinismo (6.5), que
un defecto de parseo real se manifiesta en modo mock en vez de esconderse
(6.6) y que un análisis completo en modo mock no hace ninguna llamada de red
(6.7, con `scripts/pytest_sin_red.py`).

Ningún test de este archivo llama a un LLM real ni a la red.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.agents import model_tasks
from backend.agents.agent_04_arbiter import ArbiterAgent
from backend.agents.agent_05_trials import TrialNavigatorAgent
from backend.agents.base_agent import BaseAgent, call_provider
from backend.ingestion import biomarker_extractor
from backend.mock import responses as mock_responses
from backend.mock.mode import ENV_VAR, is_mock_active
from backend.models.case import ClinicalCase
from backend.pipeline import pico

_RAIZ = Path(__file__).parent.parent
CASO_CLINICO = (
    "Paciente masculino de 42 años con neuropatía axonal sensitivomotora "
    "progresiva de 18 meses de evolución, en tratamiento con metformina."
)


# ── Activación explícita (task 6.3) ───────────────────────────────────────────

class TestActivacion:
    def test_apagado_por_defecto(self, monkeypatch):
        monkeypatch.delenv(ENV_VAR, raising=False)
        assert is_mock_active() is False

    @pytest.mark.parametrize("valor", ["1", "true", "TRUE", "on", "si"])
    def test_valores_que_activan(self, monkeypatch, valor):
        monkeypatch.setenv(ENV_VAR, valor)
        assert is_mock_active() is True

    @pytest.mark.parametrize("valor", ["0", "false", "FALSE", "no", ""])
    def test_valores_que_no_activan(self, monkeypatch, valor):
        monkeypatch.setenv(ENV_VAR, valor)
        assert is_mock_active() is False

    def test_sin_api_key_y_sin_mock_falla_claro(self, monkeypatch):
        monkeypatch.delenv(ENV_VAR, raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            call_provider(
                system_prompt="s", user_message="u", model="m",
                max_tokens=10, task="agente01_hipotesis",
            )

    def test_sin_api_key_pero_con_mock_no_falla(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "1")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        resultado = call_provider(
            system_prompt="s", user_message="u", model="m",
            max_tokens=10, task="agente01_hipotesis",
        )
        assert resultado  # devolvió algo, sin tocar Groq

    def test_con_mock_no_instancia_groq(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "1")
        with patch("groq.Groq") as groq_cls:
            call_provider(system_prompt="s", user_message="u", model="m",
                           max_tokens=10, task="agente01_hipotesis")
        groq_cls.assert_not_called()

    def test_lo_informa_al_arrancar(self, monkeypatch, capsys):
        """Spec `modo-mock-pipeline`: "Activación deliberada" se informa al arrancar."""
        import importlib

        import backend.main as main_module

        monkeypatch.setenv(ENV_VAR, "1")
        try:
            importlib.reload(main_module)
            salida = capsys.readouterr()
            assert "mock" in salida.err.lower()
        finally:
            monkeypatch.delenv(ENV_VAR, raising=False)
            importlib.reload(main_module)


# ── Las respuestas grabadas atraviesan el parseo real (task 6.1) ─────────────

class TestElModoMockEjercitaElParseoReal:
    def test_hipotesis_de_los_tres_agentes_parsean(self):
        for tarea in ("agente01_hipotesis", "agente02_hipotesis", "agente03_hipotesis"):
            hipotesis = BaseAgent.parse_hypotheses(mock_responses.get_mock_response(tarea))
            assert len(hipotesis) >= 1

    def test_critica_parsea(self):
        agente = ArbiterAgent()  # cualquier BaseAgent sirve, _parse_critiques no usa self
        criticas = agente._parse_critiques(mock_responses.get_mock_response("debate_critica"))
        assert len(criticas) == 1

    def test_pico_parsea(self):
        sintesis = pico._parse_pico(mock_responses.get_mock_response("pico_sintesis"))
        assert sintesis.condition_en == "axonal neuropathy"

    def test_biomarcadores_es_json_valido_con_las_claves_esperadas(self):
        datos = json.loads(mock_responses.get_mock_response("biomarcadores_extraccion"))
        assert "genes" in datos and "therapeutic_history" in datos

    def test_agrupacion_del_arbitro_parsea_y_extrae_groups(self):
        datos = BaseAgent.extract_json(mock_responses.get_mock_response("arbitro_agrupacion"))
        assert "groups" in datos

    def test_planificacion_de_terminos_referencia_una_candidata_valida(self):
        datos = json.loads(mock_responses.get_mock_response("agente05_planificacion_terminos"))
        assert datos["terms"][0]["candidate"] == 1

    def test_pico_build_con_mock_activo_produce_una_sintesis_real(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "1")
        case = ClinicalCase(raw_text=CASO_CLINICO)
        resultado = pico.build(case)
        assert resultado.pico is not None
        assert resultado.pico.condition_en == "axonal neuropathy"

    def test_biomarker_extract_con_mock_activo_combina_regex_y_llm(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "1")
        perfil = biomarker_extractor.extract(CASO_CLINICO)
        # La capa regex sigue funcionando sola: "metformina" no es lo que se
        # busca acá, pero el merge con la respuesta grabada no debe romper.
        assert "metformina" in [d.lower() for d in perfil.drugs]


# ── Determinismo (task 6.5) ───────────────────────────────────────────────────

class TestDeterminismo:
    def test_pico_build_es_deterministico(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "1")
        r1 = pico.build(ClinicalCase(raw_text=CASO_CLINICO))
        r2 = pico.build(ClinicalCase(raw_text=CASO_CLINICO))
        assert r1.pico == r2.pico

    def test_biomarcadores_extract_es_deterministico(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "1")
        p1 = biomarker_extractor.extract(CASO_CLINICO)
        p2 = biomarker_extractor.extract(CASO_CLINICO)
        assert p1 == p2


# ── El modo mock manifiesta un defecto de parseo real (task 6.6) ─────────────

class TestManifiestaDefectosDeParseo:
    def test_un_parser_roto_falla_tambien_en_modo_mock(self, monkeypatch):
        """
        Simula que alguien introdujo un bug en `_parse_pico` (el parseo real,
        no la respuesta grabada). Si el modo mock ejercitara ese parseo de
        verdad, el bug tiene que manifestarse acá; si el modo mock devolviera
        un resultado ya armado sin pasar por el parser, este test no
        detectaría nada.
        """
        monkeypatch.setenv(ENV_VAR, "1")

        def parser_roto(raw: str):
            raise ValueError("defecto introducido a propósito en el parser")

        monkeypatch.setattr("backend.pipeline.pico._parse_pico", parser_roto)
        with pytest.raises(ValueError, match="defecto introducido"):
            pico.build(ClinicalCase(raw_text=CASO_CLINICO))


# ── Marca del modo mock disponible para quien arma el reporte (task 6.4) ─────

class TestMarcaDeModoMock:
    def test_is_mock_active_es_lo_que_consulta_el_router(self, monkeypatch):
        """El router y `report_builder.build_export()` usan la misma función."""
        monkeypatch.delenv(ENV_VAR, raising=False)
        assert is_mock_active() is False
        monkeypatch.setenv(ENV_VAR, "1")
        assert is_mock_active() is True


# ── Un análisis completo por el endpoint, en modo mock (tasks 6.4/6.7) ───────

def _pico_de_prueba():
    from backend.models.case import PICOSynthesis
    return PICOSynthesis(
        patient_profile="Varón, 42 años", chief_complaint="neuropatía axonal",
        relevant_history=[], negative_findings=[], disease_duration="18 meses",
        current_treatments=[], procedures_done=["EMG"], comparison="No aplica",
        primary_outcome="identificar causa tratable", secondary_outcomes=[],
        biomarkers=[], genetic_findings=[], clinical_narrative=CASO_CLINICO,
    )


def _case_con_pico():
    case = ClinicalCase(raw_text=CASO_CLINICO)
    case.pico = _pico_de_prueba()
    from backend.models.biomarkers import BiomarkerProfile
    case.biomarkers = BiomarkerProfile(genes=["TTR"])
    return case


def _report_de_debate():
    from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
    from backend.models.report import AgentOutput, Report

    hipotesis = Hypothesis(
        text="Neuropatía axonal por deficiencia de vitamina B12.",
        priority=Priority.HIGH, evidence_level=EvidenceLevel.II,
        sources=[Source(title="Estudio B12", pmid="12345678")],
        rationale="Hallazgos compatibles.",
    )
    return Report(
        case_summary=CASO_CLINICO, hypotheses=[hipotesis],
        agent_outputs=[AgentOutput(agent_id="01", agent_name="Analista de Literatura",
                                    hypotheses=[hipotesis])],
        sources_summary={"I": 0, "II": 1, "III": 0},
    )


class TestAnalisisCompletoEnModoMock:
    """
    Corre `POST /api/analyze` con el modo mock activo. `pico.build()`,
    `extract_biomarkers()` y `ArbiterAgent.arbitrate()` corren de verdad —son
    los que este cambio instrumenta—; los pasos que dependen de APIs externas
    ajenas a este cambio (indexación RAG, verificación bibliográfica,
    navegación de ensayos) están mockeados al nivel de test, con el mismo
    criterio que `tests/test_api.py`.
    """

    def _correr(self, monkeypatch):
        from unittest.mock import AsyncMock

        from backend.models.trial import TrialNavigationResult, TrialSearchSummary
        from fastapi.testclient import TestClient

        from backend.main import app

        monkeypatch.setenv(ENV_VAR, "1")
        with (
            patch("backend.api.router.normalize", return_value="texto normalizado"),
            patch("backend.api.router.orchestrator.run_round_1",
                  new_callable=AsyncMock, return_value=_report_de_debate()),
            patch("backend.api.router.debate.run_debate",
                  new_callable=AsyncMock, return_value=_report_de_debate()),
            patch("backend.api.router.verify_report_sources",
                  new_callable=AsyncMock, return_value={}),
            patch("backend.api.router.TrialNavigatorAgent.navigate",
                  new_callable=AsyncMock,
                  return_value=TrialNavigationResult(summary=TrialSearchSummary(
                      estado_clinicaltrials="sin_consulta", estado_orphanet="sin_consulta",
                  ))),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            return client.post("/api/analyze", data={"text": CASO_CLINICO})

    def test_devuelve_200_y_marca_el_reporte_como_mock(self, monkeypatch):
        response = self._correr(monkeypatch)
        assert response.status_code == 200
        assert response.json()["metadata"]["mock"] is True

    def test_sin_modo_mock_el_reporte_no_esta_marcado(self, monkeypatch):
        """Complemento: un reporte real (aquí, con todo mockeado igual) no lo declara."""
        monkeypatch.delenv(ENV_VAR, raising=False)
        # No se puede correr un análisis real sin red: solo se verifica el
        # default del contrato, que ya cubre `tests/test_api.py`.
        from backend.api.schemas import ReportMetadata
        from datetime import datetime, timezone
        metadata = ReportMetadata(
            generated_at=datetime.now(timezone.utc), nexus_version="x",
            processing_time_seconds=0.1,
        )
        assert metadata.mock is False


# ── Cero llamadas de red en un análisis completo (task 6.7) ──────────────────

def test_hermetico_sin_red_analisis_completo_en_modo_mock():
    """
    Corre, en un subproceso con `scripts/pytest_sin_red.py`, los tests de este
    archivo que activan el modo mock —incluido un `POST /api/analyze`
    completo— y confirma con el mismo instrumento que ya usa
    `scripts/demo_tests_rag_hermeticos.py` (tarjeta #75) que ninguno intenta
    conectarse a la red.
    """
    import re

    entorno = dict(os.environ, PYTHONPATH=str(_RAIZ / "scripts"))

    proceso = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_mock_pipeline.py::TestActivacion",
         "tests/test_mock_pipeline.py::TestElModoMockEjercitaElParseoReal",
         "tests/test_mock_pipeline.py::TestAnalisisCompletoEnModoMock",
         "-q", "-p", "no:cacheprovider", "-p", "pytest_sin_red"],
        cwd=_RAIZ, env=entorno, capture_output=True, text=True, encoding="utf-8",
    )
    salida = proceso.stdout + proceso.stderr

    fallaron = re.search(r"(\d+) failed", salida)
    conexiones = re.search(r"intentos de conexión bloqueados: (\d+)", salida)

    assert "passed" in salida, salida
    assert fallaron is None, salida
    assert conexiones is not None and conexiones.group(1) == "0", salida
