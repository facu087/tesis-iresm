"""
Tests de la capacidad `proveedor-por-agente` (Sprint 5, OpenSpec
`multi-proveedor-por-agente`).

Sin red: los clientes de Anthropic, OpenAI, Google y Groq se reemplazan con
dobles que registran lo que reciben.
"""

from __future__ import annotations

import pytest

from backend.agents import model_tasks
from backend.agents.model_tasks import (
    AGENT_PROVIDERS,
    PROVIDER_ANTHROPIC,
    PROVIDER_GOOGLE,
    PROVIDER_OPENAI,
    TASK_BUDGETS,
    resolve_agent_provider,
    target_mode_active,
)

_ENV_PROVEEDORES = (
    "NEXUS_PROVEEDORES",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "NEXUS_MODELO_ANTHROPIC",
    "NEXUS_MODELO_OPENAI",
    "NEXUS_MODELO_GOOGLE",
)


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada test arranca sin variables de proveedor ni avisos previos."""
    for nombre in _ENV_PROVEEDORES:
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setattr(model_tasks, "_avisos_activacion", set())


# ── 2.1 Mapa por agente y activación ─────────────────────────────────────


class TestActivacion:
    def test_desactivada_por_defecto(self) -> None:
        assert target_mode_active() is False

    def test_groq_explicito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEXUS_PROVEEDORES", "groq")
        assert target_mode_active() is False

    def test_destino_sin_distinguir_mayusculas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEXUS_PROVEEDORES", " Destino ")
        assert target_mode_active() is True

    def test_valor_no_reconocido_avisa_y_queda_en_groq(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Scenario: Valor de activación no reconocido."""
        monkeypatch.setenv("NEXUS_PROVEEDORES", "claude")
        assert target_mode_active() is False
        assert target_mode_active() is False
        err = capsys.readouterr().err
        assert "NEXUS_PROVEEDORES='claude'" in err
        assert err.count("no es un valor reconocido") == 1  # una vez por valor
        assert resolve_agent_provider("01", "agente01_hipotesis") is None


class TestMapaPorAgente:
    def test_asignacion_de_la_arquitectura(self) -> None:
        """Scenario: Revisar qué proveedor usa cada agente — un solo mapa."""
        assert {k: v.provider for k, v in AGENT_PROVIDERS.items()} == {
            "01": PROVIDER_ANTHROPIC,
            "02": PROVIDER_OPENAI,
            "03": PROVIDER_GOOGLE,
            "04": PROVIDER_ANTHROPIC,
            "06": PROVIDER_ANTHROPIC,
        }

    def test_sin_activar_ningun_agente_tiene_proveedor(self) -> None:
        for agent_id in AGENT_PROVIDERS:
            assert resolve_agent_provider(agent_id, "debate_critica") is None

    @pytest.mark.parametrize("agent_id", ["05", None])
    def test_agente05_y_llamadas_sin_agente_quedan_en_groq(
        self, monkeypatch: pytest.MonkeyPatch, agent_id: str | None
    ) -> None:
        monkeypatch.setenv("NEXUS_PROVEEDORES", "destino")
        assert resolve_agent_provider(agent_id, "pico_sintesis") is None

    def test_misma_tarea_distinto_agente(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Scenario: Misma tarea, distinto agente — techo que no trunca."""
        monkeypatch.setenv("NEXUS_PROVEEDORES", "destino")
        del01 = resolve_agent_provider("01", "debate_critica")
        del02 = resolve_agent_provider("02", "debate_critica")
        assert (del01.provider, del01.model, del01.max_tokens) == (
            PROVIDER_ANTHROPIC, "claude-opus-5-5", 16000,
        )
        assert (del02.provider, del02.model) == (PROVIDER_OPENAI, "gpt-4o")
        # GPT-4o conserva el techo de la tarea (design D4).
        assert del02.max_tokens == TASK_BUDGETS["debate_critica"].max_tokens

    def test_modelo_configurable_por_proveedor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEXUS_PROVEEDORES", "destino")
        monkeypatch.setenv("NEXUS_MODELO_GOOGLE", "gemini-otro")
        assert resolve_agent_provider("03", "agente03_hipotesis").model == "gemini-otro"


# ── Dobles de los SDK ────────────────────────────────────────────────────

import contextlib  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

import anthropic  # noqa: E402
import httpx2  # noqa: E402
import openai  # noqa: E402
from google.genai import types as genai_types  # noqa: E402

from backend.agents import base_agent  # noqa: E402
from backend.agents.base_agent import ProviderRefusal, call_provider  # noqa: E402
from backend.agents.model_tasks import GROQ_FAST, GROQ_MAIN  # noqa: E402
from backend.telemetry import usage  # noqa: E402

# Fragmento que simula un pedazo del prompt dentro del mensaje de un error.
_TEXTO_DEL_PROMPT = "PACIENTE JUAN PEREZ DNI 12345678"


def _mensaje_anthropic(texto: str = "respuesta claude", stop_reason: str = "end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=texto),
        ],
        usage=SimpleNamespace(input_tokens=100, output_tokens=200),
    )


class _AnthropicDoble:
    """Imita `anthropic.Anthropic` lo justo para `_call_anthropic()`."""

    def __init__(self, mensaje=None, error: Exception | None = None) -> None:
        self.mensaje = mensaje or _mensaje_anthropic()
        self.error = error
        self.constructor: list[dict] = []
        self.pedidos: list[dict] = []

    def __call__(self, **kwargs):
        self.constructor.append(kwargs)
        doble = self

        @contextlib.contextmanager
        def stream(**pedido):
            doble.pedidos.append(pedido)
            if doble.error is not None:
                raise doble.error
            yield SimpleNamespace(get_final_message=lambda: doble.mensaje)

        return SimpleNamespace(messages=SimpleNamespace(stream=stream))


def _respuesta_chat(texto: str, finish_reason: str = "stop", refusal=None):
    respuesta = MagicMock()
    respuesta.choices = [MagicMock(
        message=MagicMock(content=texto, refusal=refusal), finish_reason=finish_reason,
    )]
    respuesta.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
    return respuesta


def _respuesta_gemini(texto: str = "respuesta gemini", finish=genai_types.FinishReason.STOP):
    return SimpleNamespace(
        candidates=[SimpleNamespace(finish_reason=finish)],
        text=texto,
        usage_metadata=SimpleNamespace(
            prompt_token_count=30, candidates_token_count=40, thoughts_token_count=5,
        ),
    )


class _Dobles:
    """Los cuatro clientes reemplazados a la vez, para mirar quién recibió qué."""

    def __init__(self) -> None:
        self.anthropic = _AnthropicDoble()
        self.openai = MagicMock()
        self.openai.chat.completions.create.return_value = _respuesta_chat("respuesta gpt")
        self.google = MagicMock()
        self.google.models.generate_content.return_value = _respuesta_gemini()
        self.groq = MagicMock()
        self.groq.chat.completions.create.return_value = _respuesta_chat("respuesta groq")
        self.openai_ctor = MagicMock(return_value=self.openai)
        self.google_ctor = MagicMock(return_value=self.google)
        self.groq_ctor = MagicMock(return_value=self.groq)

    @contextlib.contextmanager
    def activos(self):
        with patch("anthropic.Anthropic", self.anthropic), \
                patch("openai.OpenAI", self.openai_ctor), \
                patch("google.genai.Client", self.google_ctor), \
                patch("groq.Groq", self.groq_ctor):
            yield self

    def quien(self) -> dict[str, int]:
        return {
            "anthropic": len(self.anthropic.pedidos),
            "openai": self.openai.chat.completions.create.call_count,
            "google": self.google.models.generate_content.call_count,
            "groq": self.groq.chat.completions.create.call_count,
        }


@pytest.fixture
def dobles() -> _Dobles:
    with _Dobles().activos() as d:
        yield d


@pytest.fixture
def destino_con_claves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_PROVEEDORES", "destino")
    monkeypatch.setenv("GROQ_API_KEY", "groq-falsa")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-falsa")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-falsa")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-falsa")


@pytest.fixture
def registro():
    token = usage.open_registry()
    reg = usage.current()
    yield reg
    usage._current.reset(token)


def _llamar(task: str, agent_id: str | None, model: str = GROQ_MAIN, max_tokens: int = 4096) -> str:
    return call_provider(
        system_prompt="sistema", user_message="mensaje", model=model,
        max_tokens=max_tokens, task=task, agent_id=agent_id,
        agent_name=f"Agente {agent_id}" if agent_id else None,
    )


def _error_anthropic_500() -> Exception:
    respuesta = httpx2.Response(
        500, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return anthropic.InternalServerError(
        f"overloaded: {_TEXTO_DEL_PROMPT}", response=respuesta, body=None,
    )


def _error_openai_401() -> Exception:
    respuesta = httpx2.Response(
        401, request=httpx2.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    return openai.AuthenticationError("invalid api key", response=respuesta, body=None)


# ── 3.1 Adaptadores ──────────────────────────────────────────────────────


class TestAdaptadores:
    def test_anthropic_arma_el_pedido_sin_temperature(self) -> None:
        doble = _AnthropicDoble()
        with patch("anthropic.Anthropic", doble):
            resultado = base_agent._call_anthropic(
                api_key="k", system_prompt="sis", user_message="usr",
                model="claude-opus-5-5", max_tokens=16000, temperature=0.3,
            )
        pedido = doble.pedidos[0]
        assert "temperature" not in pedido
        assert pedido["output_config"] == {"effort": "medium"}
        assert pedido["system"] == "sis"
        assert pedido["messages"] == [{"role": "user", "content": "usr"}]
        assert pedido["max_tokens"] == 16000
        assert doble.constructor[0]["timeout"] == 120.0
        # El texto sale solo de los bloques de texto, no del razonamiento.
        assert resultado.text == "respuesta claude"
        assert (resultado.prompt_tokens, resultado.completion_tokens) == (100, 200)
        assert resultado.truncated is False

    def test_anthropic_marca_truncamiento(self) -> None:
        doble = _AnthropicDoble(_mensaje_anthropic(stop_reason="max_tokens"))
        with patch("anthropic.Anthropic", doble):
            resultado = base_agent._call_anthropic(
                api_key="k", system_prompt="s", user_message="u",
                model="m", max_tokens=10, temperature=0.3,
            )
        assert resultado.truncated is True

    def test_anthropic_refusal_es_una_falla(self) -> None:
        doble = _AnthropicDoble(_mensaje_anthropic(stop_reason="refusal"))
        with patch("anthropic.Anthropic", doble), pytest.raises(ProviderRefusal):
            base_agent._call_anthropic(
                api_key="k", system_prompt="s", user_message="u",
                model="m", max_tokens=10, temperature=0.3,
            )

    def test_openai_arma_el_pedido(self) -> None:
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _respuesta_chat("hola", "length")
        ctor = MagicMock(return_value=cliente)
        with patch("openai.OpenAI", ctor):
            resultado = base_agent._call_openai(
                api_key="k", system_prompt="sis", user_message="usr",
                model="gpt-4o", max_tokens=4096, temperature=0.3,
            )
        _, kwargs = cliente.chat.completions.create.call_args
        assert kwargs == {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "sis"},
                {"role": "user", "content": "usr"},
            ],
            "max_completion_tokens": 4096,
            "temperature": 0.3,
        }
        assert ctor.call_args.kwargs["timeout"] == 120.0
        assert (resultado.text, resultado.prompt_tokens, resultado.completion_tokens) == (
            "hola", 10, 20,
        )
        assert resultado.truncated is True

    def test_openai_refusal_es_una_falla(self) -> None:
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _respuesta_chat(None, refusal="no")
        with patch("openai.OpenAI", MagicMock(return_value=cliente)), \
                pytest.raises(ProviderRefusal):
            base_agent._call_openai(
                api_key="k", system_prompt="s", user_message="u",
                model="gpt-4o", max_tokens=10, temperature=0.3,
            )

    def test_google_arma_el_pedido(self) -> None:
        cliente = MagicMock()
        cliente.models.generate_content.return_value = _respuesta_gemini(
            finish=genai_types.FinishReason.MAX_TOKENS,
        )
        ctor = MagicMock(return_value=cliente)
        with patch("google.genai.Client", ctor):
            resultado = base_agent._call_google(
                api_key="k", system_prompt="sis", user_message="usr",
                model="gemini-3.1-pro-preview", max_tokens=16000, temperature=0.3,
            )
        _, kwargs = cliente.models.generate_content.call_args
        assert kwargs["model"] == "gemini-3.1-pro-preview"
        assert kwargs["contents"] == "usr"
        assert kwargs["config"].system_instruction == "sis"
        assert kwargs["config"].max_output_tokens == 16000
        assert kwargs["config"].temperature is None
        assert ctor.call_args.kwargs["http_options"].timeout == 120_000  # milisegundos
        # Los tokens de razonamiento se cobran como salida.
        assert (resultado.prompt_tokens, resultado.completion_tokens) == (30, 45)
        assert resultado.text == "respuesta gemini"
        assert resultado.truncated is True

    def test_google_bloqueado_es_una_falla(self) -> None:
        cliente = MagicMock()
        cliente.models.generate_content.return_value = _respuesta_gemini(
            texto=None, finish=genai_types.FinishReason.SAFETY,
        )
        with patch("google.genai.Client", MagicMock(return_value=cliente)), \
                pytest.raises(ProviderRefusal):
            base_agent._call_google(
                api_key="k", system_prompt="s", user_message="u",
                model="m", max_tokens=10, temperature=0.3,
            )


# ── 3.2 Resolución y respaldo en call_provider() ─────────────────────────


@pytest.mark.usefixtures("destino_con_claves")
class TestDestinoActivo:
    def test_llamada_de_un_agente_con_proveedor_asignado(self, dobles, registro) -> None:
        """Scenario: Llamada de un agente con proveedor asignado."""
        assert _llamar("debate_critica", "02") == "respuesta gpt"
        assert dobles.quien() == {"anthropic": 0, "openai": 1, "google": 0, "groq": 0}
        _, kwargs = dobles.openai.chat.completions.create.call_args
        assert kwargs["model"] == "gpt-4o"
        llamada = registro.calls[-1]
        assert (llamada.provider, llamada.model, llamada.fallback) == ("openai", "gpt-4o", False)

    def test_debate_con_tres_proveedores(self, dobles) -> None:
        """Scenario: Debate con tres proveedores."""
        assert _llamar("debate_critica", "01") == "respuesta claude"
        assert _llamar("debate_critica", "02") == "respuesta gpt"
        assert _llamar("debate_critica", "03") == "respuesta gemini"
        assert dobles.quien() == {"anthropic": 1, "openai": 1, "google": 1, "groq": 0}

    def test_misma_tarea_distinto_agente_usa_el_techo_de_cada_modelo(self, dobles) -> None:
        """Scenario: Misma tarea, distinto agente."""
        _llamar("debate_critica", "01")
        _llamar("debate_critica", "02")
        assert dobles.anthropic.pedidos[0]["max_tokens"] == 16000
        _, kwargs = dobles.openai.chat.completions.create.call_args
        assert kwargs["max_completion_tokens"] == 4096

    def test_sintesis_pico_sigue_en_groq(self, dobles) -> None:
        """Scenario: Síntesis PICO con la arquitectura de destino activa."""
        assert _llamar("pico_sintesis", None, max_tokens=2048) == "respuesta groq"
        assert dobles.quien() == {"anthropic": 0, "openai": 0, "google": 0, "groq": 1}

    def test_agente05_sigue_en_groq(self, dobles) -> None:
        """Scenario: Agente 05 con la arquitectura de destino activa."""
        _llamar("agente05_planificacion_terminos", "05", model=GROQ_FAST)
        assert dobles.quien() == {"anthropic": 0, "openai": 0, "google": 0, "groq": 1}
        _, kwargs = dobles.groq.chat.completions.create.call_args
        assert kwargs["model"] == GROQ_FAST

    def test_falta_la_clave_de_google(
        self, dobles, registro, monkeypatch, capsys,
    ) -> None:
        """Scenario: Falta la clave de Google."""
        monkeypatch.delenv("GOOGLE_API_KEY")
        assert _llamar("agente03_hipotesis", "03") == "respuesta groq"
        _llamar("debate_critica", "03")
        assert dobles.quien()["google"] == 0
        err = capsys.readouterr().err
        assert "Agente 03" in err and "falta GOOGLE_API_KEY" in err
        assert err.count("respaldo") == 1  # una vez por análisis y proveedor
        llamada = registro.calls[-1]
        assert (llamada.provider, llamada.fallback, llamada.fallback_reason) == (
            "groq", True, "clave_faltante",
        )
        assert llamada.model == GROQ_MAIN

    def test_ninguna_clave_de_destino(self, dobles, registro, monkeypatch) -> None:
        """Scenario: Ninguna clave de destino."""
        for nombre in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
            monkeypatch.delenv(nombre)
        for agent_id in ("01", "02", "03", "04", "06"):
            assert _llamar("debate_critica", agent_id) == "respuesta groq"
        assert dobles.quien() == {"anthropic": 0, "openai": 0, "google": 0, "groq": 5}
        assert all(c.provider == "groq" and c.fallback for c in registro.calls)

    def test_anthropic_no_responde(self, dobles, registro) -> None:
        """Scenario: Anthropic no responde."""
        dobles.anthropic.error = _error_anthropic_500()
        assert _llamar("arbitro_veredictos", "04") == "respuesta groq"
        fallida, respaldo = registro.calls
        assert (fallida.provider, fallida.ok, fallida.model) == (
            "anthropic", False, "claude-opus-5-5",
        )
        assert (respaldo.provider, respaldo.ok, respaldo.fallback_reason) == (
            "groq", True, "falla",
        )

    def test_clave_invalida(self, dobles, registro) -> None:
        """Scenario: Clave inválida."""
        dobles.openai.chat.completions.create.side_effect = _error_openai_401()
        assert _llamar("agente02_hipotesis", "02") == "respuesta groq"
        assert registro.calls[-1].fallback_reason == "falla"

    def test_aviso_de_falla_sin_el_mensaje_del_error(self, dobles, registro, capsys) -> None:
        """Scenario: Aviso de falla del proveedor."""
        dobles.anthropic.error = _error_anthropic_500()
        _llamar("agente01_hipotesis", "01")
        err = capsys.readouterr().err
        assert "InternalServerError" in err
        assert _TEXTO_DEL_PROMPT not in err
        assert _TEXTO_DEL_PROMPT not in repr(registro.calls)

    def test_falla_de_groq_en_el_respaldo_se_propaga(self, dobles) -> None:
        dobles.anthropic.error = _error_anthropic_500()
        dobles.groq.chat.completions.create.side_effect = RuntimeError("groq caído")
        with pytest.raises(RuntimeError, match="groq caído"):
            _llamar("agente01_hipotesis", "01")


class TestSinActivar:
    def test_sin_activar_con_claves_presentes(self, dobles, registro, monkeypatch) -> None:
        """Scenario: Sin activar, con claves presentes — lo que llega a Groq es lo de hoy."""
        monkeypatch.setenv("GROQ_API_KEY", "groq-falsa")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-falsa")
        assert _llamar("agente01_hipotesis", "01") == "respuesta groq"
        assert dobles.quien() == {"anthropic": 0, "openai": 0, "google": 0, "groq": 1}
        assert dobles.anthropic.constructor == []
        _, kwargs = dobles.groq.chat.completions.create.call_args
        assert kwargs == {
            "model": GROQ_MAIN,
            "messages": [
                {"role": "system", "content": "sistema"},
                {"role": "user", "content": "mensaje"},
            ],
            "max_tokens": 4096,
            "temperature": 0.3,
        }
        llamada = registro.calls[-1]
        assert (llamada.provider, llamada.fallback, llamada.fallback_reason) == (
            "groq", False, None,
        )


# ── 3.3 Un solo lugar instancia un cliente de proveedor ──────────────────

# Constructores de cliente de los cuatro SDK.
_CONSTRUCTORES = (
    "Groq(", "Anthropic(", "OpenAI(", "genai.Client(",
)
_RAIZ = Path(__file__).resolve().parent.parent


def _instanciaciones(raiz: Path) -> list[str]:
    """`ruta:línea` de cada constructor de cliente de proveedor bajo `raiz/backend`."""
    encontradas = []
    for ruta in sorted((raiz / "backend").rglob("*.py")):
        for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            codigo = linea.split("#", 1)[0]
            if any(c in codigo for c in _CONSTRUCTORES) and "class " not in codigo:
                encontradas.append(f"{ruta.relative_to(raiz)}:{numero}")
    return encontradas


class TestPuntoUnico:
    def test_solo_base_agent_instancia_clientes(self) -> None:
        lugares = _instanciaciones(_RAIZ)
        assert lugares, "el escaneo no encontró ni el cliente de Groq"
        assert {lugar.split(":")[0] for lugar in lugares} == {"backend/agents/base_agent.py"}
        assert len(lugares) == 4  # uno por SDK

    def test_detecta_un_cliente_fuera_de_base_agent(self, tmp_path: Path) -> None:
        (tmp_path / "backend" / "pipeline").mkdir(parents=True)
        (tmp_path / "backend" / "pipeline" / "nuevo.py").write_text(
            "import openai\ncliente = openai.OpenAI(api_key='x')\n", encoding="utf-8",
        )
        assert _instanciaciones(tmp_path) == ["backend/pipeline/nuevo.py:2"]


# ── 3.4 Modo mock ────────────────────────────────────────────────────────


class TestModoMock:
    def test_modo_mock_con_la_arquitectura_de_destino_activa(
        self, dobles, destino_con_claves, monkeypatch,
    ) -> None:
        """Scenario: Modo mock con la arquitectura de destino activa."""
        from backend.mock import responses

        monkeypatch.setenv("NEXUS_MOCK_LLM", "1")
        # Sin sesión de reproducción abierta, la grabación elegida es siempre la misma.
        esperada = responses.get_mock_response("agente01_hipotesis", agent_id="01")
        resultado = _llamar("agente01_hipotesis", "01")
        assert dobles.quien() == {"anthropic": 0, "openai": 0, "google": 0, "groq": 0}
        assert dobles.anthropic.constructor == []
        assert isinstance(resultado, str) and resultado
        assert resultado == esperada


# ── 5.1 Grabación y modo mock con proveedor ──────────────────────────────


class TestGrabacionConProveedor:
    def test_el_grabador_guarda_proveedor_y_modelo(self, dobles, destino_con_claves) -> None:
        from backend.mock import recorder

        token = recorder.open_recorder()
        try:
            _llamar("agente01_hipotesis", "01")
            entrada = recorder.current().entries[-1]
        finally:
            recorder._current.reset(token)
        assert (entrada["provider"], entrada["model"]) == ("anthropic", "claude-opus-5-5")
        assert "user_message" not in entrada and "system_prompt" not in entrada

    def test_el_modo_mock_reproduce_el_proveedor_grabado(
        self, monkeypatch, tmp_path, registro,
    ) -> None:
        import json

        from backend.mock import responses

        archivo = tmp_path / "grabadas.json"
        archivo.write_text(json.dumps({"tasks": {"agente01_hipotesis": [{
            "seq": 1, "agent_id": "01", "provider": "anthropic",
            "model": "claude-opus-5-5", "response": "{\"hypotheses\": []}",
        }]}}), encoding="utf-8")
        monkeypatch.setattr(responses, "_ARCHIVO_GRABADAS", archivo)
        monkeypatch.setattr(responses, "_CACHE", None)
        monkeypatch.setenv("NEXUS_MOCK_LLM", "1")
        assert _llamar("agente01_hipotesis", "01") == "{\"hypotheses\": []}"
        llamada = registro.calls[-1]
        assert (llamada.provider, llamada.model, llamada.mock) == (
            "anthropic", "claude-opus-5-5", True,
        )

    def test_grabadas_json_actual_carga_y_se_reproduce_como_groq(
        self, monkeypatch, registro,
    ) -> None:
        from backend.mock import responses

        monkeypatch.setattr(responses, "_CACHE", None)
        monkeypatch.setenv("NEXUS_MOCK_LLM", "1")
        _llamar("agente01_hipotesis", "01")
        llamada = registro.calls[-1]
        assert (llamada.provider, llamada.model) == ("groq", GROQ_MAIN)
