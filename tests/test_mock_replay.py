"""
Tests de la reproducción de una corrida grabada en modo mock
(`backend/mock/responses.py`): elección de la respuesta por agente y por número
de llamada, y sesión de reproducción por análisis.

Cubre:
  - con varias grabaciones de una tarea, cada agente recibe la suya;
  - con varias grabaciones de (tarea, agente), la n-ésima llamada recibe la
    n-ésima grabación por `seq`, y pasado el final se repite la última;
  - un agente sin grabación para la tarea recibe la primera de la tarea;
  - el conteo es por análisis: dos sesiones seguidas dan la misma secuencia, y
    sin sesión abierta la elección no guarda estado;
  - la sesión se comparte entre las tareas de `asyncio.gather()` y los
    `asyncio.to_thread()` con los que el pipeline llama al proveedor;
  - `call_provider()` pasa el agente que llama;
  - el debate real (Rondas 2 a 4) sobre un archivo de varias grabaciones.

Todos los archivos de datos son sintéticos y temporales: ningún test toca
`backend/mock/grabadas.json`, llama a un LLM ni usa la red.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.agents.base_agent import call_provider
from backend.mock import responses as mock_responses
from backend.mock.mode import ENV_VAR
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority
from backend.models.report import AgentOutput, Report
from backend.pipeline import debate

AGENTES = ("01", "02", "03")


def _entrada(seq: int, agent_id: str | None, texto: str) -> dict:
    """Una entrada con la forma de las de `grabadas.json`."""
    return {
        "agent_id": agent_id, "model": "modelo-x", "seq": seq,
        "recorded_at": "2026-10-06", "response": texto,
    }


@pytest.fixture
def grabadas(monkeypatch, tmp_path):
    """Devuelve una función que escribe `tasks` en un archivo de datos temporal."""
    destino = tmp_path / "grabadas.json"
    monkeypatch.setattr(mock_responses, "_ARCHIVO_GRABADAS", destino)
    monkeypatch.setattr(mock_responses, "_CACHE", None)

    def escribir(tareas: dict) -> None:
        destino.write_text(
            json.dumps({"tasks": tareas}, ensure_ascii=False), encoding="utf-8"
        )
        mock_responses._CACHE = None

    return escribir


@pytest.fixture(autouse=True)
def _sin_sesion_abierta():
    """Ningún test hereda una sesión de reproducción abierta de otro."""
    assert mock_responses.current_replay_session() is None
    yield
    assert mock_responses.current_replay_session() is None


@pytest.fixture
def sesion():
    """Abre una sesión de reproducción y la cierra al terminar el test."""
    token = mock_responses.open_replay_session()
    yield mock_responses.current_replay_session()
    mock_responses.close_replay_session(token)


# ── Elección por agente y por número de llamada ───────────────────────────────

class TestEleccion:
    def test_cada_agente_recibe_su_grabacion(self, grabadas):
        grabadas({"t": [_entrada(6, "01", "de-01"), _entrada(7, "02", "de-02")]})
        assert mock_responses.get_mock_response("t", agent_id="01") == "de-01"
        assert mock_responses.get_mock_response("t", agent_id="02") == "de-02"

    def test_el_mismo_agente_recibe_primera_segunda_y_despues_la_ultima(
        self, grabadas, sesion
    ):
        grabadas({"t": [_entrada(9, "01", "primera"), _entrada(12, "01", "segunda")]})
        recibidas = [mock_responses.get_mock_response("t", agent_id="01") for _ in range(4)]
        assert recibidas == ["primera", "segunda", "segunda", "segunda"]

    def test_un_agente_sin_grabacion_recibe_la_primera_por_seq(self, grabadas, sesion):
        grabadas({"t": [_entrada(8, "02", "tardia"), _entrada(6, "01", "temprana")]})
        assert mock_responses.get_mock_response("t", agent_id="03") == "temprana"
        assert mock_responses.get_mock_response("t", agent_id="03") == "temprana"
        assert mock_responses.get_mock_response("t") == "temprana"  # sin agente

    def test_el_orden_es_el_de_seq_y_no_el_del_archivo(self, grabadas, sesion):
        grabadas({"t": [_entrada(12, "01", "segunda"), _entrada(9, "01", "primera")]})
        assert mock_responses.get_mock_response("t", agent_id="01") == "primera"
        assert mock_responses.get_mock_response("t", agent_id="01") == "segunda"

    def test_las_llamadas_sin_agente_tienen_su_propia_secuencia(self, grabadas, sesion):
        """PICO y biomarcadores llaman sin agente: `agent_id` nulo en la grabación."""
        grabadas({"t": [_entrada(1, None, "a"), _entrada(2, None, "b"),
                        _entrada(3, "01", "de-01")]})
        assert [mock_responses.get_mock_response("t") for _ in range(3)] == ["a", "b", "b"]
        assert mock_responses.get_mock_response("t", agent_id="01") == "de-01"

    def test_el_conteo_es_por_tarea_y_por_agente(self, grabadas, sesion):
        grabadas({
            "t": [_entrada(1, "01", "t-01-a"), _entrada(2, "02", "t-02-a"),
                  _entrada(3, "01", "t-01-b"), _entrada(4, "02", "t-02-b")],
            "u": [_entrada(5, "01", "u-01-a"), _entrada(6, "01", "u-01-b")],
        })
        assert mock_responses.get_mock_response("t", agent_id="01") == "t-01-a"
        assert mock_responses.get_mock_response("u", agent_id="01") == "u-01-a"
        assert mock_responses.get_mock_response("t", agent_id="02") == "t-02-a"
        assert mock_responses.get_mock_response("t", agent_id="01") == "t-01-b"
        assert mock_responses.get_mock_response("t", agent_id="02") == "t-02-b"
        assert mock_responses.get_mock_response("u", agent_id="01") == "u-01-b"

    def test_la_forma_de_una_sola_entrada_sirve_a_cualquier_agente(self, grabadas, sesion):
        """Es la forma del archivo versionado: una entrada por tarea."""
        grabadas({"t": _entrada(6, "01", "unica")})
        for agente in (None, *AGENTES):
            for _ in range(2):
                assert mock_responses.get_mock_response("t", agent_id=agente) == "unica"

    def test_una_tarea_desconocida_sigue_devolviendo_el_json_vacio(self, grabadas, sesion):
        grabadas({"t": [_entrada(1, "01", "x")]})
        assert mock_responses.get_mock_response("otra", agent_id="01") == "{}"


# ── Sesión de reproducción por análisis ───────────────────────────────────────

class TestSesion:
    def test_abrir_activa_y_cerrar_desactiva(self):
        token = mock_responses.open_replay_session()
        assert mock_responses.current_replay_session() is not None
        mock_responses.close_replay_session(token)
        assert mock_responses.current_replay_session() is None

    def test_abrir_una_sesion_no_lee_el_archivo_de_datos(self, grabadas):
        """La operación real abre la sesión igual y nunca toca el archivo."""
        token = mock_responses.open_replay_session()  # el archivo ni siquiera existe
        mock_responses.close_replay_session(token)
        assert mock_responses._CACHE is None

    def test_sin_sesion_abierta_la_eleccion_no_guarda_estado(self, grabadas):
        grabadas({"t": [_entrada(9, "01", "primera"), _entrada(12, "01", "segunda")]})
        recibidas = [mock_responses.get_mock_response("t", agent_id="01") for _ in range(3)]
        assert recibidas == ["primera", "primera", "primera"]
        assert mock_responses.current_replay_session() is None  # no crea una implícita

    def test_dos_sesiones_seguidas_reciben_la_misma_secuencia(self, grabadas):
        grabadas({"t": [_entrada(9, "01", "primera"), _entrada(12, "01", "segunda"),
                        _entrada(10, "02", "de-02")]})

        def analisis() -> list[str]:
            token = mock_responses.open_replay_session()
            try:
                return [
                    mock_responses.get_mock_response("t", agent_id=agente)
                    for agente in ("01", "02", "01", "01")
                ]
            finally:
                mock_responses.close_replay_session(token)

        primero, segundo = analisis(), analisis()
        assert primero == ["primera", "de-02", "segunda", "segunda"]
        assert segundo == primero

    def test_cerrar_restaura_la_sesion_anterior(self, grabadas):
        """Una sesión anidada (una rama de la comparación) no arrastra el conteo."""
        grabadas({"t": [_entrada(1, "01", "a"), _entrada(2, "01", "b")]})
        externa = mock_responses.open_replay_session()
        assert mock_responses.get_mock_response("t", agent_id="01") == "a"
        interna = mock_responses.open_replay_session()
        assert mock_responses.get_mock_response("t", agent_id="01") == "a"
        mock_responses.close_replay_session(interna)
        assert mock_responses.get_mock_response("t", agent_id="01") == "b"
        mock_responses.close_replay_session(externa)

    @pytest.mark.asyncio
    async def test_las_tareas_de_gather_comparten_el_conteo(self, grabadas):
        """Misma primitiva que el debate: `gather` + `to_thread`, una ronda tras otra."""
        pares = [(ronda, agente) for ronda in (3, 4) for agente in AGENTES]
        grabadas({"t": [
            _entrada(seq, agente, f"{agente}-ronda{ronda}")
            for seq, (ronda, agente) in enumerate(pares, start=1)
        ]})

        async def ronda() -> list[str]:
            return await asyncio.gather(*(
                asyncio.to_thread(mock_responses.get_mock_response, "t", agent_id=agente)
                for agente in AGENTES
            ))

        token = mock_responses.open_replay_session()
        try:
            assert await ronda() == ["01-ronda3", "02-ronda3", "03-ronda3"]
            # El conteo que hicieron los threads de la ronda anterior se ve acá:
            # con un conteo propio de cada tarea se repetiría la ronda 3.
            assert await ronda() == ["01-ronda4", "02-ronda4", "03-ronda4"]
            assert mock_responses.get_mock_response("t", agent_id="01") == "01-ronda4"
        finally:
            mock_responses.close_replay_session(token)


# ── Enganche en call_provider() ───────────────────────────────────────────────

def _llamar(task: str, agent_id: str | None) -> str:
    return call_provider(
        system_prompt="s", user_message="u", model="m", max_tokens=10,
        task=task, agent_id=agent_id, agent_name="Agente de prueba",
    )


class TestCallProvider:
    def test_pasa_el_agente_que_llama(self, grabadas, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "1")
        grabadas({"t": [_entrada(6, "01", "de-01"), _entrada(7, "02", "de-02")]})
        assert _llamar("t", "02") == "de-02"
        assert _llamar("t", "01") == "de-01"
        assert _llamar("t", None) == "de-01"  # sin agente: la primera por seq

    def test_dentro_de_una_sesion_avanza_por_llamada(self, grabadas, monkeypatch, sesion):
        monkeypatch.setenv(ENV_VAR, "1")
        grabadas({"t": [_entrada(9, "01", "primera"), _entrada(12, "01", "segunda")]})
        assert [_llamar("t", "01") for _ in range(3)] == ["primera", "segunda", "segunda"]


# ── El debate real sobre un archivo de varias grabaciones ─────────────────────

def _hipotesis_json(texto: str) -> str:
    return json.dumps({"hypotheses": [{
        "text": texto, "priority": "MEDIUM", "evidence_level": "III",
        "rationale": "Fundamento de prueba.", "sources": [],
    }]}, ensure_ascii=False)


def _critica_json(destinatario: str, autor: str) -> str:
    return json.dumps({"critiques": [{
        "target_agent_id": destinatario,
        "target_hypothesis": f"Hipótesis inicial del agente {destinatario}",
        "critique_text": f"Objeción del agente {autor}.",
        "severity": "LOW", "alternative": None,
    }]}, ensure_ascii=False)


def _tareas_del_debate() -> dict:
    """Una crítica y dos revisiones (Rondas 3 y 4) por agente, como en una corrida real."""
    criticas = [
        _entrada(6 + i, agente, _critica_json(AGENTES[(i + 1) % 3], agente))
        for i, agente in enumerate(AGENTES)
    ]
    revisiones = [
        _entrada(9 + 3 * (ronda - 3) + i, agente,
                 _hipotesis_json(f"Revisión del agente {agente} en la ronda {ronda}"))
        for ronda in (3, 4)
        for i, agente in enumerate(AGENTES)
    ]
    return {"debate_critica": criticas, "debate_revision": revisiones}


def _caso() -> ClinicalCase:
    case = ClinicalCase(raw_text="Caso de prueba.")
    case.pico = PICOSynthesis(
        patient_profile="Varón, 42 años", chief_complaint="neuropatía axonal",
        relevant_history=[], negative_findings=[], disease_duration="18 meses",
        current_treatments=[], procedures_done=[], comparison="No aplica",
        primary_outcome="identificar causa tratable", secondary_outcomes=[],
        biomarkers=[], genetic_findings=[], clinical_narrative="Caso de prueba.",
    )
    return case


def _ronda_1() -> Report:
    salidas = [
        AgentOutput(agent_id=agente, agent_name=f"Agente {agente}", hypotheses=[
            Hypothesis(text=f"Hipótesis inicial del agente {agente}",
                       priority=Priority.MEDIUM, evidence_level=EvidenceLevel.III,
                       rationale="Fundamento de prueba."),
        ])
        for agente in AGENTES
    ]
    return Report(
        case_summary="Caso de prueba.",
        hypotheses=[h for s in salidas for h in s.hypotheses],
        agent_outputs=salidas, sources_summary={"I": 0, "II": 0, "III": 0},
    )


def _resumen(report: Report) -> dict:
    """Lo que el debate dejó, en una forma comparable entre corridas."""
    return {
        "criticas": [(c.from_agent_id, c.target_agent_id, c.critique_text)
                     for c in report.debate_rounds[0].critiques],
        "rondas": {
            r.round_number: {s.agent_id: [h.text for h in s.hypotheses]
                             for s in r.agent_outputs}
            for r in report.debate_rounds[1:]
        },
        "finales": [h.text for h in report.hypotheses],
    }


class TestDebateSobreVariasGrabaciones:
    async def _debatir(self) -> dict:
        token = mock_responses.open_replay_session()
        try:
            return _resumen(await debate.run_debate(_caso(), _ronda_1()))
        finally:
            mock_responses.close_replay_session(token)

    @pytest.mark.asyncio
    async def test_cada_agente_recibe_su_critica_y_su_revision_de_cada_ronda(
        self, grabadas, monkeypatch
    ):
        monkeypatch.setenv(ENV_VAR, "1")
        grabadas(_tareas_del_debate())

        resumen = await self._debatir()

        assert sorted(resumen["criticas"]) == [
            ("01", "02", "Objeción del agente 01."),
            ("02", "03", "Objeción del agente 02."),
            ("03", "01", "Objeción del agente 03."),
        ]
        for ronda in (3, 4):
            assert resumen["rondas"][ronda] == {
                agente: [f"Revisión del agente {agente} en la ronda {ronda}"]
                for agente in AGENTES
            }
        assert resumen["finales"] == [
            f"Revisión del agente {agente} en la ronda 4" for agente in AGENTES
        ]

    @pytest.mark.asyncio
    async def test_dos_debates_seguidos_dan_el_mismo_resultado(self, grabadas, monkeypatch):
        """`modo-mock-pipeline` — Requirement: Resultado determinista."""
        monkeypatch.setenv(ENV_VAR, "1")
        grabadas(_tareas_del_debate())
        corridas = [await self._debatir() for _ in range(5)]
        assert all(c == corridas[0] for c in corridas[1:])
