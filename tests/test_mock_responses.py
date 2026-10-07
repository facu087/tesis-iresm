"""
Tests de las respuestas del modo mock (control de costos, Sprint 4 — tarea 6.2).

Las respuestas de `backend/mock/responses.py` salen todas de una corrida real
contra Groq (`backend/mock/grabadas.json`, texto crudo y sin retocar). Acá se
verifica:

  - el contrato de `MOCK_RESPONSES` (una respuesta por tarea de `TASK_BUDGETS`);
  - que lo grabado es fiel al archivo de datos y trae su procedencia;
  - que cada respuesta atraviesa el parseo real de su sitio de llamada sin
    caer en el fallback ni descartarse en silencio.

Ningún test llama a un LLM real ni a la red.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

from backend.agents import model_tasks
from backend.agents.agent_04_arbiter import _PMID_EN_TEXTO, ArbiterAgent
from backend.agents.agent_05_trials import TrialNavigatorAgent
from backend.agents.base_agent import BaseAgent
from backend.ingestion import biomarker_extractor
from backend.mock import responses as mock_responses
from backend.mock.mode import ENV_VAR
from backend.models.arbitration import ArbitrationInput, ArbitrationStatus
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority
from backend.models.trial import ClinicalTrial, TrialCandidate, TrialNavigationInput
from backend.pipeline import pico

_ARCHIVO = Path(mock_responses.__file__).with_name("grabadas.json")

# Todas las tareas del presupuesto salen de la grabación: ninguna está escrita a mano.
_ESPERADAS_GRABADAS = set(model_tasks.TASK_BUDGETS)


@pytest.fixture(autouse=True)
def _modo_mock(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "1")


# ── Contrato de MOCK_RESPONSES ────────────────────────────────────────────────

class TestContrato:
    def test_una_respuesta_no_vacia_por_cada_tarea_del_presupuesto(self):
        assert set(mock_responses.MOCK_RESPONSES) == set(model_tasks.TASK_BUDGETS)
        for tarea, texto in mock_responses.MOCK_RESPONSES.items():
            assert isinstance(texto, str) and texto.strip(), tarea

    def test_get_mock_response_mantiene_el_fallback_para_tareas_desconocidas(self):
        assert mock_responses.get_mock_response("tarea_que_no_existe") == "{}"

    def test_las_trece_tareas_salen_de_la_grabacion_y_ninguna_esta_escrita_a_mano(self):
        assert len(model_tasks.TASK_BUDGETS) == 13
        assert set(mock_responses.RECORDED_RESPONSES) == _ESPERADAS_GRABADAS
        assert not hasattr(mock_responses, "HAND_WRITTEN_TASKS")
        assert mock_responses.MOCK_RESPONSES == {
            tarea: entrada["response"]
            for tarea, entrada in mock_responses.RECORDED_RESPONSES.items()
        }


# ── Fidelidad de lo grabado ───────────────────────────────────────────────────

def _entradas_del_archivo(tarea: str) -> list[dict]:
    """Entradas de `tarea` leídas del archivo, tenga una sola o una lista."""
    entrada = json.loads(_ARCHIVO.read_text(encoding="utf-8"))["tasks"][tarea]
    return entrada if isinstance(entrada, list) else [entrada]


class TestGrabacionFiel:
    def test_el_archivo_de_datos_esta_versionado_y_es_utf8(self):
        assert _ARCHIVO.is_file()
        json.loads(_ARCHIVO.read_text(encoding="utf-8"))

    @pytest.mark.parametrize("tarea", sorted(_ESPERADAS_GRABADAS))
    def test_la_respuesta_es_el_texto_del_archivo_sin_retocar(self, tarea):
        entradas = _entradas_del_archivo(tarea)
        primera = min(entradas, key=lambda e: e["seq"])
        assert mock_responses.MOCK_RESPONSES[tarea] == primera["response"]
        assert sorted(_grabaciones(tarea)) == sorted(e["response"] for e in entradas)

    @pytest.mark.parametrize("tarea", sorted(_ESPERADAS_GRABADAS))
    def test_cada_entrada_trae_su_procedencia(self, tarea):
        for entrada in _entradas_del_archivo(tarea):
            assert entrada["model"].startswith("openai/gpt-oss-")
            assert isinstance(entrada["seq"], int)
            assert "agent_id" in entrada
            assert entrada["recorded_at"] == "2026-10-07"

    @pytest.mark.parametrize("tarea", sorted(_ESPERADAS_GRABADAS))
    def test_el_modelo_de_la_grabacion_coincide_con_el_presupuesto_de_la_tarea(self, tarea):
        """Una respuesta de `gpt-oss-20b` no puede hacerse pasar por una de `120b`."""
        for entrada in _entradas_del_archivo(tarea):
            assert entrada["model"] == model_tasks.TASK_BUDGETS[tarea].model

    def test_el_archivo_versionado_trae_la_corrida_completa_por_agente(self):
        """
        Grabación del 2026-10-07: las tareas del debate tienen una entrada por
        llamada, con su agente, y cada agente recibe la suya (no la de otro).
        """
        entradas = mock_responses.get_recorded_entries()
        autores = {e["agent_id"] for e in entradas["debate_critica"]}
        assert autores == {"01", "02", "03"}
        assert len(entradas["debate_revision"]) == 6
        for tarea in ("debate_critica", "debate_revision", "debate_recitacion"):
            for agente in {e["agent_id"] for e in entradas[tarea]}:
                propia = next(e for e in entradas[tarea] if e["agent_id"] == agente)
                assert mock_responses.get_mock_response(tarea, agent_id=agente) == propia["response"]

    def test_ninguna_critica_grabada_apunta_a_su_autor(self):
        for entrada in mock_responses.get_recorded_entries()["debate_critica"]:
            criticas = ArbiterAgent()._parse_critiques(entrada["response"])
            assert criticas
            assert entrada["agent_id"] not in {c.target_agent_id for c in criticas}

    def test_las_respuestas_conservan_el_formato_crudo_del_modelo(self):
        """Un JSON re-serializado por nosotros no traería sangría de dos espacios."""
        assert "\n  " in mock_responses.MOCK_RESPONSES["pico_sintesis"]
        assert "\\u" not in _ARCHIVO.read_text(encoding="utf-8")


# ── Cada respuesta atraviesa el parseo real de su sitio de llamada ────────────

def _hipotesis(n: int) -> list[Hypothesis]:
    return [
        Hypothesis(
            text=f"Hipótesis de prueba {i + 1}", priority=Priority.MEDIUM,
            evidence_level=EvidenceLevel.III, rationale="Fundamento de prueba.",
        )
        for i in range(n)
    ]


def _entrada_arbitro(n: int) -> ArbitrationInput:
    return ArbitrationInput(
        hypotheses=_hipotesis(n), hypothesis_agents=["01"] * n,
        agent_names={"01": "Analista de Literatura"},
    )


def _grabaciones(tarea: str) -> list[str]:
    """
    Todas las respuestas grabadas de `tarea`, en orden de `seq`.

    El modo mock puede devolver cualquiera de ellas según el agente y el número
    de llamada, así que las verificaciones de parseo recorren todas y no solo la
    primera.
    """
    entradas = mock_responses.get_recorded_entries()[tarea]
    assert entradas, tarea
    return [entrada["response"] for entrada in entradas]


@pytest.fixture
def sesion_de_reproduccion():
    """
    Sesión de reproducción abierta durante el test: dentro de ella, la n-ésima
    llamada de un agente a una tarea recibe su n-ésima grabación, y así un test
    que llama una vez por grabación las recorre todas.
    """
    token = mock_responses.open_replay_session()
    yield
    mock_responses.close_replay_session(token)


class TestTodasLasGrabacionesSeVerifican:
    """Las verificaciones de parseo alcanzan a cada entrada de un archivo con varias."""

    def test_grabaciones_expone_cada_entrada_de_una_tarea_con_varias(self, archivo_de_datos):
        archivo_de_datos.write_text(json.dumps({"tasks": {
            "t": [
                {"agent_id": "02", "model": "m", "seq": 7, "recorded_at": "x", "response": "b"},
                {"agent_id": "01", "model": "m", "seq": 6, "recorded_at": "x", "response": "a"},
                {"agent_id": "01", "model": "m", "seq": 9, "recorded_at": "x", "response": "c"},
            ],
            "u": {"agent_id": "04", "model": "m", "seq": 1, "recorded_at": "x", "response": "d"},
        }}), encoding="utf-8")
        assert _grabaciones("t") == ["a", "b", "c"]
        assert _grabaciones("u") == ["d"]

    def test_una_grabacion_que_no_parsea_se_detecta_aunque_no_sea_la_primera(
        self, archivo_de_datos
    ):
        buena = json.dumps({"hypotheses": [{
            "text": "Hipótesis", "priority": "LOW", "evidence_level": "III",
            "rationale": "Fundamento.", "sources": [],
        }]})
        archivo_de_datos.write_text(json.dumps({"tasks": {"debate_revision": [
            {"agent_id": "01", "model": "m", "seq": 1, "recorded_at": "x", "response": buena},
            {"agent_id": "02", "model": "m", "seq": 2, "recorded_at": "x",
             "response": '{"hypotheses": []}'},
        ]}}), encoding="utf-8")
        # El parser real rechaza una respuesta sin hipótesis con un ValueError.
        with pytest.raises(ValueError):
            TestParseoRealPorSitioDeLlamada().test_hipotesis_parsean_y_no_quedan_vacias(
                "debate_revision"
            )


class TestParseoRealPorSitioDeLlamada:
    @pytest.mark.parametrize("tarea", ["agente01_hipotesis", "agente02_hipotesis",
                                       "agente03_hipotesis", "debate_revision"])
    def test_hipotesis_parsean_y_no_quedan_vacias(self, tarea):
        for respuesta in _grabaciones(tarea):
            hipotesis = BaseAgent.parse_hypotheses(respuesta)
            assert len(hipotesis) >= 1
            assert all(h.text.strip() for h in hipotesis)

    def test_cada_critica_grabada_parsea_con_ids_canonicos(self):
        for respuesta in _grabaciones("debate_critica"):
            criticas = ArbiterAgent()._parse_critiques(respuesta)
            assert criticas
            assert all(re.fullmatch(r"\d{2}", c.target_agent_id) for c in criticas)

    def test_la_critica_grabada_parsea_con_ids_canonicos(self):
        """El modelo real nombra "Agent 02"; el parser real lo lleva a "02"."""
        criticas = ArbiterAgent()._parse_critiques(mock_responses.get_mock_response("debate_critica"))
        assert len(criticas) == 8
        assert all(re.fullmatch(r"\d{2}", c.target_agent_id) for c in criticas)
        assert sorted(c.target_agent_id for c in criticas) == ["02"] * 3 + ["03"] * 5

    def test_la_critica_grabada_llega_a_un_agente_del_debate(self):
        from backend.pipeline.debate import _critiques_for

        criticas = ArbiterAgent()._parse_critiques(mock_responses.get_mock_response("debate_critica"))
        assert len(_critiques_for("02", criticas)) == 3
        assert len(_critiques_for("03", criticas)) == 5
        assert _critiques_for("01", criticas) == []  # nadie critica al autor de la grabación

    def test_recitacion_parsea_con_fuentes(self):
        for respuesta in _grabaciones("debate_recitacion"):
            recitadas = ArbiterAgent()._parse_recitation(respuesta, total=3)
            assert recitadas and all(fuentes for fuentes in recitadas.values())

    def test_pico_parsea(self):
        for respuesta in _grabaciones("pico_sintesis"):
            sintesis = pico._parse_pico(respuesta)
            assert sintesis.condition_en and sintesis.clinical_narrative

    # Los cuatro tests que siguen llegan a la grabación a través de
    # `call_provider()`: llaman una vez por grabación dentro de una sesión de
    # reproducción, que les entrega una distinta en cada llamada.

    def test_biomarcadores_extract_combina_regex_y_respuesta_grabada(
        self, sesion_de_reproduccion
    ):
        for _ in _grabaciones("biomarcadores_extraccion"):
            perfil = biomarker_extractor.extract("Paciente con neuropatía axonal progresiva.")
            assert perfil.antibodies  # los que aportó la respuesta grabada

    def test_agrupacion_no_cae_en_el_estado_degradado(self, sesion_de_reproduccion):
        agente = ArbiterAgent()
        for _ in _grabaciones("arbitro_agrupacion"):
            grupos, estado = asyncio.run(agente._group(_entrada_arbitro(14)))
            assert estado is ArbitrationStatus.OK
            assert sorted(i for g in grupos for i in g) == list(range(14))  # nadie se pierde

    def test_veredictos_ninguno_cita_un_pmid_que_lo_descartaria(self):
        for respuesta in _grabaciones("arbitro_veredictos"):
            datos = BaseAgent.extract_json(respuesta)
            veredictos = datos["verdicts"]
            assert veredictos
            for item in veredictos:
                assert isinstance(item["hypothesis"], int)
                assert item["verdict"].strip()
                assert not _PMID_EN_TEXTO.findall(item["verdict"])

    def test_planificacion_de_terminos_produce_planes(self, sesion_de_reproduccion):
        agente = TrialNavigatorAgent()
        entrada = TrialNavigationInput(
            condition_en="axonal neuropathy",
            candidates=[
                TrialCandidate(text=f"Candidata {i}", priority=Priority.HIGH,
                               evidence_level=EvidenceLevel.III)
                for i in range(3)
            ],
        )
        for _ in _grabaciones("agente05_planificacion_terminos"):
            planes, estado = asyncio.run(agente._plan_terms(entrada))
            assert estado == "ok" and planes

    def test_evaluacion_de_compatibilidad_conserva_el_ensayo_que_nombra(
        self, sesion_de_reproduccion
    ):
        """El NCT que la grabación evalúa sobrevive a la validación si fue enviado."""
        agente = TrialNavigatorAgent()
        for respuesta in _grabaciones("agente05_evaluacion_compatibilidad"):
            datos = json.loads(respuesta)
            nct = datos["evaluations"][0]["nct_id"]
            ensayo = ClinicalTrial(nct_id=nct, title="Ensayo de prueba", status="RECRUITING",
                                   brief_summary="Resumen.")
            evaluaciones, estado, descartadas = asyncio.run(
                agente._evaluate(TrialNavigationInput(), [ensayo])
            )
            assert estado == "ok" and nct in evaluaciones
            assert evaluaciones[nct].compatibility in {"alta", "media", "baja"}
            assert descartadas == len(datos["evaluations"]) - 1  # solo los no enviados


# ── Carga diferida del archivo de datos ───────────────────────────────────────

_REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def archivo_de_datos(monkeypatch, tmp_path):
    """Apunta el cargador a un archivo temporal y descarta la caché al terminar."""
    destino = tmp_path / "grabadas.json"
    monkeypatch.setattr(mock_responses, "_ARCHIVO_GRABADAS", destino)
    monkeypatch.setattr(mock_responses, "_CACHE", None)
    return destino


class TestCargaDiferida:
    def test_importar_los_agentes_no_lee_el_archivo_de_datos(self):
        """Prueba en un proceso limpio: cualquier lectura de `grabadas.json` falla."""
        import subprocess
        import sys

        codigo = (
            "from pathlib import Path\n"
            "orig = Path.read_text\n"
            "def guardia(self, *a, **k):\n"
            "    if self.name == 'grabadas.json':\n"
            "        raise AssertionError('se leyó grabadas.json al importar')\n"
            "    return orig(self, *a, **k)\n"
            "Path.read_text = guardia\n"
            "import backend.agents.base_agent\n"
            "import backend.mock.responses as r\n"
            "assert r._CACHE is None\n"
        )
        resultado = subprocess.run(
            [sys.executable, "-c", codigo], cwd=_REPO, capture_output=True, text=True
        )
        assert resultado.returncode == 0, resultado.stderr

    def test_camino_real_no_toca_el_archivo_aunque_este_roto(
        self, archivo_de_datos, monkeypatch
    ):
        from unittest.mock import MagicMock, patch

        from backend.agents.base_agent import call_provider

        archivo_de_datos.write_text("{ esto no es json", encoding="utf-8")
        monkeypatch.delenv(ENV_VAR, raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "clave-falsa")
        respuesta = MagicMock()
        respuesta.choices = [MagicMock()]
        respuesta.choices[0].message.content = "{}"
        respuesta.usage.prompt_tokens = 1
        respuesta.usage.completion_tokens = 1
        with patch("groq.Groq") as groq:
            groq.return_value.chat.completions.create.return_value = respuesta
            call_provider(system_prompt="s", user_message="u", model="m",
                          max_tokens=10, task="pico_sintesis")
        assert mock_responses._CACHE is None

    def test_el_archivo_se_lee_una_sola_vez(self, archivo_de_datos):
        archivo_de_datos.write_text(
            json.dumps({"tasks": {"t": {"response": "{\"a\": 1}"}}}), encoding="utf-8"
        )
        assert mock_responses.get_mock_response("t") == '{"a": 1}'
        archivo_de_datos.unlink()  # una segunda lectura fallaría
        assert mock_responses.get_mock_response("t") == '{"a": 1}'
        assert mock_responses.MOCK_RESPONSES == {"t": '{"a": 1}'}
        assert set(mock_responses.RECORDED_RESPONSES) == {"t"}

    def test_archivo_ausente_falla_con_el_error_claro(self, archivo_de_datos):
        with pytest.raises(mock_responses.RespuestasGrabadasInvalidas) as e:
            mock_responses.get_mock_response("pico_sintesis")
        assert "grabadas.json" in str(e.value)

    @pytest.mark.parametrize("contenido", [
        "{ esto no es json",
        "[]",
        "{}",
        '{"tasks": []}',
        '{"tasks": {"t": "texto"}}',
        '{"tasks": {"t": {}}}',
        '{"tasks": {"t": {"response": ""}}}',
        '{"tasks": {"t": {"response": "   "}}}',
        '{"tasks": {"t": {"response": 3}}}',
    ])
    def test_archivo_malformado_falla_con_el_error_claro(self, archivo_de_datos, contenido):
        archivo_de_datos.write_text(contenido, encoding="utf-8")
        with pytest.raises(mock_responses.RespuestasGrabadasInvalidas) as e:
            mock_responses.get_mock_response("t")
        assert "grabadas.json" in str(e.value)

    def test_acepta_una_tarea_con_una_lista_de_entradas(self, archivo_de_datos):
        archivo_de_datos.write_text(json.dumps({"tasks": {
            "varias": [
                {"agent_id": "02", "model": "m", "seq": 7, "recorded_at": "x", "response": "b"},
                {"agent_id": None, "model": "m", "seq": 6, "recorded_at": "x", "response": "a"},
            ],
            "una": {"agent_id": "04", "model": "m", "seq": 1, "recorded_at": "x",
                    "response": "c"},
        }}), encoding="utf-8")
        todas = mock_responses.get_recorded_entries()
        assert [e["response"] for e in todas["varias"]] == ["a", "b"]  # por seq
        assert [e["response"] for e in todas["una"]] == ["c"]
        # La vista de una entrada por tarea toma la primera por seq.
        assert mock_responses.RECORDED_RESPONSES["varias"]["seq"] == 6
        assert mock_responses.MOCK_RESPONSES == {"varias": "a", "una": "c"}

    @pytest.mark.parametrize("entradas", [
        [],
        ["texto"],
        [{"agent_id": "01", "seq": 1}],
        [{"agent_id": "01", "seq": 1, "response": ""}],
        [{"agent_id": "01", "seq": 1, "response": 3}],
        [{"agent_id": "01", "response": "a"}],
        [{"agent_id": "01", "seq": "1", "response": "a"}],
        [{"agent_id": "01", "seq": True, "response": "a"}],
        [{"agent_id": "01", "seq": 1.5, "response": "a"}],
        [{"seq": 1, "response": "a"}],
        [{"agent_id": 1, "seq": 1, "response": "a"}],
        [{"agent_id": "01", "seq": 1, "response": "a"},
         {"agent_id": "02", "seq": 1, "response": "b"}],
        [{"agent_id": "01", "seq": 1, "response": "a"}, "texto"],
        [[{"agent_id": "01", "seq": 1, "response": "a"}]],
    ])
    def test_una_lista_malformada_falla_con_el_error_claro(self, archivo_de_datos, entradas):
        archivo_de_datos.write_text(json.dumps({"tasks": {"t": entradas}}), encoding="utf-8")
        with pytest.raises(mock_responses.RespuestasGrabadasInvalidas) as e:
            mock_responses.get_mock_response("t")
        assert "grabadas.json" in str(e.value)
        assert mock_responses._CACHE is None

    def test_un_fallo_no_deja_una_cache_a_medias(self, archivo_de_datos):
        archivo_de_datos.write_text("{ roto", encoding="utf-8")
        with pytest.raises(mock_responses.RespuestasGrabadasInvalidas):
            mock_responses.get_mock_response("t")
        assert mock_responses._CACHE is None
        archivo_de_datos.write_text(
            json.dumps({"tasks": {"t": {"response": "{}"}}}), encoding="utf-8"
        )
        assert mock_responses.get_mock_response("t") == "{}"

    def test_el_error_no_contiene_texto_de_respuestas(self, archivo_de_datos):
        archivo_de_datos.write_text(
            '{"tasks": {"t": {"response": 3, "x": "SECRETO-CLINICO"}}}', encoding="utf-8"
        )
        with pytest.raises(mock_responses.RespuestasGrabadasInvalidas) as e:
            mock_responses.get_mock_response("t")
        assert "SECRETO-CLINICO" not in str(e.value)

    def test_un_nombre_inexistente_del_modulo_sigue_siendo_attribute_error(self):
        with pytest.raises(AttributeError):
            mock_responses.NO_EXISTE  # noqa: B018
