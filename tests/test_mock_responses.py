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

    def test_las_doce_tareas_salen_de_la_grabacion_y_ninguna_esta_escrita_a_mano(self):
        assert len(model_tasks.TASK_BUDGETS) == 12
        assert set(mock_responses.RECORDED_RESPONSES) == _ESPERADAS_GRABADAS
        assert not hasattr(mock_responses, "HAND_WRITTEN_TASKS")
        assert mock_responses.MOCK_RESPONSES == {
            tarea: entrada["response"]
            for tarea, entrada in mock_responses.RECORDED_RESPONSES.items()
        }


# ── Fidelidad de lo grabado ───────────────────────────────────────────────────

class TestGrabacionFiel:
    def test_el_archivo_de_datos_esta_versionado_y_es_utf8(self):
        assert _ARCHIVO.is_file()
        json.loads(_ARCHIVO.read_text(encoding="utf-8"))

    @pytest.mark.parametrize("tarea", sorted(_ESPERADAS_GRABADAS))
    def test_la_respuesta_es_el_texto_del_archivo_sin_retocar(self, tarea):
        datos = json.loads(_ARCHIVO.read_text(encoding="utf-8"))
        assert mock_responses.MOCK_RESPONSES[tarea] == datos["tasks"][tarea]["response"]

    @pytest.mark.parametrize("tarea", sorted(_ESPERADAS_GRABADAS))
    def test_cada_entrada_trae_su_procedencia(self, tarea):
        entrada = json.loads(_ARCHIVO.read_text(encoding="utf-8"))["tasks"][tarea]
        assert entrada["model"].startswith("openai/gpt-oss-")
        assert isinstance(entrada["seq"], int)
        assert "agent_id" in entrada
        assert entrada["recorded_at"] == "2026-10-06"

    def test_el_modelo_de_la_grabacion_coincide_con_el_presupuesto_de_la_tarea(self):
        """Una respuesta de `gpt-oss-20b` no puede hacerse pasar por una de `120b`."""
        datos = json.loads(_ARCHIVO.read_text(encoding="utf-8"))["tasks"]
        for tarea, entrada in datos.items():
            assert entrada["model"] == model_tasks.TASK_BUDGETS[tarea].model, tarea

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


class TestParseoRealPorSitioDeLlamada:
    @pytest.mark.parametrize("tarea", ["agente01_hipotesis", "agente02_hipotesis",
                                       "agente03_hipotesis", "debate_revision"])
    def test_hipotesis_parsean_y_no_quedan_vacias(self, tarea):
        hipotesis = BaseAgent.parse_hypotheses(mock_responses.get_mock_response(tarea))
        assert len(hipotesis) >= 1
        assert all(h.text.strip() for h in hipotesis)

    def test_la_critica_grabada_parsea_con_ids_canonicos(self):
        """El modelo real nombra "Agent 02"; el parser real lo lleva a "02"."""
        criticas = ArbiterAgent()._parse_critiques(mock_responses.get_mock_response("debate_critica"))
        assert len(criticas) == 5
        assert all(re.fullmatch(r"\d{2}", c.target_agent_id) for c in criticas)
        assert sorted(c.target_agent_id for c in criticas) == ["02", "02", "03", "03", "03"]

    def test_la_critica_grabada_llega_a_un_agente_del_debate(self):
        from backend.pipeline.debate import _critiques_for

        criticas = ArbiterAgent()._parse_critiques(mock_responses.get_mock_response("debate_critica"))
        assert len(_critiques_for("02", criticas)) == 2
        assert len(_critiques_for("03", criticas)) == 3
        assert _critiques_for("01", criticas) == []  # nadie critica al autor de la grabación

    def test_recitacion_parsea_con_fuentes(self):
        recitadas = ArbiterAgent()._parse_recitation(
            mock_responses.get_mock_response("debate_recitacion"), total=3
        )
        assert recitadas and all(fuentes for fuentes in recitadas.values())

    def test_pico_parsea(self):
        sintesis = pico._parse_pico(mock_responses.get_mock_response("pico_sintesis"))
        assert sintesis.condition_en and sintesis.clinical_narrative

    def test_biomarcadores_extract_combina_regex_y_respuesta_grabada(self):
        perfil = biomarker_extractor.extract("Paciente con neuropatía axonal progresiva.")
        assert perfil.antibodies  # los que aportó la respuesta grabada

    def test_agrupacion_no_cae_en_el_estado_degradado(self):
        agente = ArbiterAgent()
        grupos, estado = asyncio.run(agente._group(_entrada_arbitro(14)))
        assert estado is ArbitrationStatus.OK
        assert sorted(i for g in grupos for i in g) == list(range(14))  # nadie se pierde

    def test_veredictos_ninguno_cita_un_pmid_que_lo_descartaria(self):
        datos = BaseAgent.extract_json(mock_responses.get_mock_response("arbitro_veredictos"))
        veredictos = datos["verdicts"]
        assert veredictos
        for item in veredictos:
            assert isinstance(item["hypothesis"], int)
            assert item["verdict"].strip()
            assert not _PMID_EN_TEXTO.findall(item["verdict"])

    def test_planificacion_de_terminos_produce_planes(self):
        agente = TrialNavigatorAgent()
        entrada = TrialNavigationInput(
            condition_en="axonal neuropathy",
            candidates=[
                TrialCandidate(text=f"Candidata {i}", priority=Priority.HIGH,
                               evidence_level=EvidenceLevel.III)
                for i in range(3)
            ],
        )
        planes, estado = asyncio.run(agente._plan_terms(entrada))
        assert estado == "ok" and planes

    def test_evaluacion_de_compatibilidad_conserva_el_ensayo_que_nombra(self):
        """El NCT que la grabación evalúa sobrevive a la validación si fue enviado."""
        datos = json.loads(mock_responses.get_mock_response("agente05_evaluacion_compatibilidad"))
        nct = datos["evaluations"][0]["nct_id"]
        ensayo = ClinicalTrial(nct_id=nct, title="Ensayo de prueba", status="RECRUITING",
                               brief_summary="Resumen.")
        agente = TrialNavigatorAgent()
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
