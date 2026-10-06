"""
Tests de las respuestas del modo mock (control de costos, Sprint 4 — tarea 6.2).

Las respuestas de `backend/mock/responses.py` salen, salvo las que se listan en
`HAND_WRITTEN_TASKS`, de una corrida real contra Groq (`backend/mock/grabadas.json`,
texto crudo y sin retocar). Acá se verifica:

  - el contrato de `MOCK_RESPONSES` (una respuesta por tarea de `TASK_BUDGETS`);
  - que lo grabado es fiel al archivo de datos y trae su procedencia;
  - que cada respuesta atraviesa el parseo real de su sitio de llamada sin
    caer en el fallback ni descartarse en silencio.

Ningún test llama a un LLM real ni a la red.
"""

from __future__ import annotations

import asyncio
import json
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

# Tareas cuya respuesta sale de la grabación, y la única que sigue escrita a
# mano (ver el docstring de `responses.py`: sus críticas reales nunca llegan a
# su destinatario).
_ESPERADAS_GRABADAS = set(model_tasks.TASK_BUDGETS) - {"debate_critica"}
_ESPERADAS_A_MANO = {"debate_critica"}


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

    def test_el_reparto_entre_grabadas_y_escritas_a_mano_es_el_documentado(self):
        assert set(mock_responses.RECORDED_RESPONSES) == _ESPERADAS_GRABADAS
        assert set(mock_responses.HAND_WRITTEN_TASKS) == _ESPERADAS_A_MANO
        assert not set(mock_responses.RECORDED_RESPONSES) & set(mock_responses.HAND_WRITTEN_TASKS)


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

    def test_critica_a_mano_llega_a_su_destinatario(self):
        """Por eso no se usa la grabada: `debate_critica` tiene que enrutarse por ID."""
        from backend.pipeline.debate import _critiques_for

        criticas = ArbiterAgent()._parse_critiques(mock_responses.get_mock_response("debate_critica"))
        assert len(_critiques_for("01", criticas)) >= 1

    def test_las_criticas_reales_no_se_enrutan_por_id(self):
        """
        Documenta el hallazgo que justifica dejar `debate_critica` escrita a mano:
        el modelo real nombra a su destinatario ("Agent 02", "Agent01") y
        `_critiques_for()` compara contra el ID ("02"), así que ninguna llega.
        """
        from backend.pipeline.debate import _critiques_for

        nombres = ("Agent 02", "Agent01", "Agent03")
        reales = [
            type("C", (), {"target_agent_id": n})() for n in nombres  # sin red ni modelo
        ]
        assert not any(_critiques_for(i, reales) for i in ("01", "02", "03"))  # type: ignore[arg-type]

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
