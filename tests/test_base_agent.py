"""
Tests de la clase base de agentes (backend/agents/base_agent.py).

Cubre el parseo de la respuesta del LLM: extracción del JSON, construcción de
hipótesis y, sobre todo, el **saneamiento de las fuentes** (hallazgo G). Cubre
también `call_provider()`, el punto único de llamada al proveedor (S4, control
de costos): reintentos ante 429 y delegación de `_call_llm()`. Ningún test
llama a un LLM ni a la red: las respuestas se construyen a mano.

Caso de prueba base: neuropatía axonal sensitivomotora, paciente masculino de 42 años.
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from groq import RateLimitError as GroqRateLimitError

from backend.agents import model_tasks
from backend.agents.base_agent import BaseAgent, call_provider
from backend.models.hypothesis import EvidenceLevel, Priority
from backend.telemetry import usage

_HIPOTESIS_BASE = (
    "Déficit de vitamina B12 inducido por metformina en varón de 42 años "
    "con neuropatía axonal sensitivomotora."
)


def _respuesta(sources: list[dict] | None = None) -> str:
    """Arma una respuesta JSON válida del modelo con las fuentes dadas."""
    return json.dumps({
        "hypotheses": [{
            "text": _HIPOTESIS_BASE,
            "priority": "HIGH",
            "evidence_level": "II",
            "rationale": "La metformina interfiere con la absorción ileal de B12.",
            "sources": sources if sources is not None else [],
        }]
    })


# ── Saneamiento de fuentes (hallazgo G) ───────────────────────────────────────

class TestSaneamientoDeFuentes:
    """
    Los campos de verificación son salida de PubMed, nunca entrada del modelo.

    Antes del fix, `Source(**s)` aceptaba lo que el LLM escribiera y el dato
    autodeclarado viajaba en el Report interno hasta que evidence.py lo ignoraba.
    """

    def test_verified_autodeclarado_se_descarta(self):
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "verified": True,
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert source.verified is None

    def test_verification_status_autodeclarado_se_descarta(self):
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "verification_status": "verificada",
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert source.verification_status is None

    def test_tipos_de_publicacion_inventados_se_descartan(self):
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "publication_types": ["Meta-Analysis", "Randomized Controlled Trial"],
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert source.publication_types == []

    def test_actual_title_autodeclarado_se_descarta(self):
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "actual_title": "Cualquier cosa que el modelo haya escrito",
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert source.actual_title is None

    def test_los_cuatro_campos_juntos_se_descartan(self):
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "verified": True,
            "verification_status": "verificada",
            "actual_title": "Otro título",
            "publication_types": ["Meta-Analysis"],
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert (source.verified, source.verification_status, source.actual_title) == (
            None, None, None,
        )
        assert source.publication_types == []

    def test_los_campos_declarables_se_conservan(self):
        """El saneamiento no debe llevarse puesto lo que el agente sí debe citar."""
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "journal": "Diabetes Care",
            "year": 2012,
            "url": "https://pubmed.ncbi.nlm.nih.gov/22439958/",
            "verified": True,
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert source.pmid == "22439958"
        assert source.title == "Metformin-associated vitamin B12 deficiency"
        assert source.journal == "Diabetes Care"
        assert source.year == 2012
        assert source.url == "https://pubmed.ncbi.nlm.nih.gov/22439958/"

    def test_campo_desconocido_no_rompe_el_parseo(self):
        """Un campo de más no invalida la hipótesis: no se descartan hipótesis."""
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "confianza_del_modelo": 0.97,
        }])
        hypotheses = BaseAgent.parse_hypotheses(raw)
        assert len(hypotheses) == 1
        assert hypotheses[0].sources[0].pmid == "22439958"

    def test_fuente_sin_titulo_sigue_siendo_error(self):
        """Comportamiento previo al fix: una fuente sin título no valida."""
        raw = _respuesta([{"pmid": "22439958"}])
        with pytest.raises(Exception):
            BaseAgent.parse_hypotheses(raw)


# ── Extracción de JSON ────────────────────────────────────────────────────────

class TestExtractJson:

    def test_json_puro(self):
        assert BaseAgent.extract_json('{"a": 1}') == {"a": 1}

    def test_fence_de_markdown_con_lenguaje(self):
        assert BaseAgent.extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_fence_de_markdown_sin_lenguaje(self):
        assert BaseAgent.extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_json_embebido_en_texto_libre(self):
        raw = 'Claro, acá va el análisis:\n{"a": 1}\nEspero que sirva.'
        assert BaseAgent.extract_json(raw) == {"a": 1}

    def test_sin_json_lanza_error(self):
        with pytest.raises(ValueError, match="no contiene JSON válido"):
            BaseAgent.extract_json("No encontré nada relevante.")


# ── Parseo de hipótesis ───────────────────────────────────────────────────────

class TestParseHypotheses:

    def test_hipotesis_valida(self):
        hypothesis = BaseAgent.parse_hypotheses(_respuesta())[0]
        assert hypothesis.text == _HIPOTESIS_BASE
        assert hypothesis.priority is Priority.HIGH
        assert hypothesis.evidence_level is EvidenceLevel.II
        assert hypothesis.sources == []

    def test_sin_hipotesis_lanza_error(self):
        with pytest.raises(ValueError, match="ninguna hipótesis"):
            BaseAgent.parse_hypotheses('{"hypotheses": []}')

    def test_hipotesis_sin_campo_obligatorio_lanza_error(self):
        raw = json.dumps({"hypotheses": [{"text": "Algo", "priority": "HIGH"}]})
        with pytest.raises(ValueError, match="malformada"):
            BaseAgent.parse_hypotheses(raw)

    def test_prioridad_invalida_lanza_error(self):
        raw = json.dumps({"hypotheses": [{
            "text": _HIPOTESIS_BASE,
            "priority": "URGENTÍSIMA",
            "evidence_level": "II",
            "rationale": "…",
        }]})
        with pytest.raises(ValueError):
            BaseAgent.parse_hypotheses(raw)

    def test_varias_hipotesis_conservan_el_orden(self):
        raw = json.dumps({"hypotheses": [
            {"text": f"Hipótesis {i}", "priority": "LOW",
             "evidence_level": "III", "rationale": "…"}
            for i in range(3)
        ]})
        textos = [h.text for h in BaseAgent.parse_hypotheses(raw)]
        assert textos == ["Hipótesis 0", "Hipótesis 1", "Hipótesis 2"]


# ── call_provider(): punto único de llamada al proveedor (S4) ─────────────────

def _fake_response(content: str, *, prompt_tokens=10, completion_tokens=5,
                    finish_reason="stop") -> MagicMock:
    """Imita lo justo de la respuesta de Groq que usa call_provider()."""
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content), finish_reason=finish_reason)]
    response.usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return response


def _rate_limit_error() -> GroqRateLimitError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return GroqRateLimitError("rate limited (simulado)", response=response, body=None)


class TestCallProvider:
    """
    `call_provider()` es el único lugar que instancia `Groq(api_key=...)`
    (D1): `_call_llm()`, `pico.build()` y `_extract_with_llm()` delegan acá.
    """

    def test_devuelve_el_contenido_de_la_respuesta(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _fake_response("hola")
        with patch("groq.Groq", return_value=cliente):
            resultado = call_provider(
                system_prompt="sistema", user_message="usuario",
                model="modelo-x", max_tokens=123, task="tarea_de_prueba",
            )
        assert resultado == "hola"
        _, kwargs = cliente.chat.completions.create.call_args
        assert kwargs["model"] == "modelo-x"
        assert kwargs["max_tokens"] == 123

    def test_reintenta_ante_rate_limit_y_despues_responde(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
        monkeypatch.setattr("time.sleep", lambda *_: None)
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = [
            _rate_limit_error(), _fake_response("segundo intento"),
        ]
        with patch("groq.Groq", return_value=cliente):
            resultado = call_provider(
                system_prompt="s", user_message="u", model="m",
                max_tokens=10, task="tarea_de_prueba",
            )
        assert resultado == "segundo intento"
        assert cliente.chat.completions.create.call_count == 2

    def test_agota_reintentos_y_relanza(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
        monkeypatch.setattr("time.sleep", lambda *_: None)
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = _rate_limit_error()
        with patch("groq.Groq", return_value=cliente):
            with pytest.raises(GroqRateLimitError):
                call_provider(
                    system_prompt="s", user_message="u", model="m",
                    max_tokens=10, task="tarea_de_prueba",
                )
        assert cliente.chat.completions.create.call_count == 4  # 1 + 3 reintentos

    def test_call_llm_delega_en_call_provider_con_el_presupuesto_de_la_tarea(self, monkeypatch):
        """
        `_call_llm()` resuelve modelo y techo desde `model_tasks` según la
        `task` que le pasa el llamador (D6), no desde `self.MODEL`: la
        política vigente vive en un solo mapa, consultable sin recorrer los
        agentes.
        """
        capturado = {}

        def falso(**kwargs):
            capturado.update(kwargs)
            return "respuesta"

        monkeypatch.setattr("backend.agents.base_agent.call_provider", falso)

        class AgenteDePrueba(BaseAgent):
            AGENT_ID = "99"
            AGENT_NAME = "Agente de Prueba"
            MODEL = "modelo-del-agente"  # no debe usarse: manda el mapa de tareas
            SYSTEM_PROMPT = "prompt de sistema"

            def run(self, clinical_context: str):  # pragma: no cover - no se usa
                raise NotImplementedError

        resultado = AgenteDePrueba()._call_llm("mensaje de usuario", task="agente01_hipotesis")
        assert resultado == "respuesta"
        assert capturado["model"] == model_tasks.GROQ_MAIN
        assert capturado["max_tokens"] == model_tasks.get_budget("agente01_hipotesis").max_tokens
        assert capturado["system_prompt"] == "prompt de sistema"
        assert capturado["user_message"] == "mensaje de usuario"
        assert capturado["agent_id"] == "99"
        assert capturado["task"] == "agente01_hipotesis"

    def test_call_llm_sin_task_falla(self):
        """`task` es obligatorio: todo sitio de llamada declara su tarea (D6)."""
        class AgenteDePrueba(BaseAgent):
            AGENT_ID = "99"
            AGENT_NAME = "Agente de Prueba"
            SYSTEM_PROMPT = "s"

            def run(self, clinical_context: str):  # pragma: no cover
                raise NotImplementedError

        with pytest.raises(TypeError):
            AgenteDePrueba()._call_llm("mensaje")  # type: ignore[call-arg]

    def test_call_llm_con_tarea_desconocida_falla_claro(self):
        class AgenteDePrueba(BaseAgent):
            AGENT_ID = "99"
            AGENT_NAME = "Agente de Prueba"
            SYSTEM_PROMPT = "s"

            def run(self, clinical_context: str):  # pragma: no cover
                raise NotImplementedError

        with pytest.raises(KeyError):
            AgenteDePrueba()._call_llm("mensaje", task="tarea_que_no_existe")


class TestCallProviderTelemetria:
    """`call_provider()` registra cada intento en el registro activo (D2)."""

    def test_sin_registro_activo_no_falla(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _fake_response("ok")
        assert usage.current() is None
        with patch("groq.Groq", return_value=cliente):
            resultado = call_provider(
                system_prompt="s", user_message="u", model="m",
                max_tokens=10, task="tarea_de_prueba",
            )
        assert resultado == "ok"
        assert usage.current() is None

    def test_llamada_exitosa_registra_tokens_y_agente(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _fake_response(
            "ok", prompt_tokens=42, completion_tokens=7,
        )
        token = usage.open_registry()
        try:
            with patch("groq.Groq", return_value=cliente):
                call_provider(
                    system_prompt="s", user_message="u", model="mi-modelo",
                    max_tokens=10, task="mi_tarea",
                    agent_id="07", agent_name="Agente de Prueba",
                )
            registro = usage.current()
            assert len(registro.calls) == 1
            llamada = registro.calls[0]
            assert llamada.ok is True
            assert llamada.model == "mi-modelo"
            assert llamada.task == "mi_tarea"
            assert llamada.agent_id == "07"
            assert llamada.prompt_tokens == 42
            assert llamada.completion_tokens == 7
        finally:
            usage.close_registry(token, output_path="/dev/null")

    def test_respuesta_sin_usage_se_registra_marcada(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
        respuesta = MagicMock()
        respuesta.choices = [MagicMock(message=MagicMock(content="ok"), finish_reason="stop")]
        respuesta.usage = None
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = respuesta
        token = usage.open_registry()
        try:
            with patch("groq.Groq", return_value=cliente):
                call_provider(system_prompt="s", user_message="u", model="m",
                               max_tokens=10, task="t")
            llamada = usage.current().calls[0]
            assert llamada.ok is True
            assert llamada.prompt_tokens is None
            assert llamada.completion_tokens is None
        finally:
            usage.close_registry(token, output_path="/dev/null")

    def test_respuesta_cortada_por_techo_se_marca_truncada(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _fake_response(
            "respuesta cortada a la mit", finish_reason="length",
        )
        token = usage.open_registry()
        try:
            with patch("groq.Groq", return_value=cliente):
                call_provider(system_prompt="s", user_message="u", model="m",
                               max_tokens=5, task="t")
            assert usage.current().calls[0].truncated is True
        finally:
            usage.close_registry(token, output_path="/dev/null")

    def test_reintento_por_rate_limit_deja_un_intento_fallido_y_uno_exitoso(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
        monkeypatch.setattr("time.sleep", lambda *_: None)
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = [
            _rate_limit_error(), _fake_response("ok"),
        ]
        token = usage.open_registry()
        try:
            with patch("groq.Groq", return_value=cliente):
                call_provider(system_prompt="s", user_message="u", model="m",
                               max_tokens=10, task="t")
            registro = usage.current()
            assert len(registro.calls) == 2
            assert [c.ok for c in registro.calls] == [False, True]
        finally:
            usage.close_registry(token, output_path="/dev/null")

    def test_fallo_no_reintentable_tambien_queda_contabilizado(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = ConnectionError("caído")
        token = usage.open_registry()
        try:
            with patch("groq.Groq", return_value=cliente):
                with pytest.raises(ConnectionError):
                    call_provider(system_prompt="s", user_message="u", model="m",
                                   max_tokens=10, task="t")
            registro = usage.current()
            assert len(registro.calls) == 1
            assert registro.calls[0].ok is False
        finally:
            usage.close_registry(token, output_path="/dev/null")
