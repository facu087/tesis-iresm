"""
Tests del grabador de respuestas del modelo (backend/mock/recorder.py) y de su
enganche en `call_provider()` y en `scripts/medir_costos.py --grabar`.

Cubre:
  - el grabador vive en un contexto (contextvars), igual que la telemetría: se
    abre, se consulta y se cierra explícitamente, y sin uno abierto no hace nada;
  - el contexto se propaga a `asyncio.to_thread()` y a `asyncio.gather()`, que son
    las primitivas con las que el orquestador llama al proveedor;
  - `call_provider()` entrega al grabador solo la respuesta del modelo (nunca el
    prompt ni el mensaje del usuario), solo ante una llamada real exitosa;
  - en modo mock no se graba, y un fallo del grabador no rompe la llamada;
  - el archivo JSON de salida y que un fallo al escribirlo nunca levanta;
  - la opción `--grabar` del script, incluida la preservación de una grabación
    previa y el aviso en modo mock.

Ningún test llama a un LLM ni a la red.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.base_agent import call_provider
from backend.mock import recorder

_RAIZ = Path(__file__).parent.parent

RESPUESTA = "RESPUESTA-CRUDA-DEL-MODELO"
PROMPT_SISTEMA = "PROMPT-DE-SISTEMA-SECRETO"
MENSAJE_USUARIO = "MENSAJE-CLINICO-DEL-USUARIO"


@pytest.fixture(autouse=True)
def _sin_grabador_activo():
    """Ningún test hereda un grabador abierto de otro."""
    assert recorder.current() is None
    yield
    assert recorder.current() is None


def _fake_response(content: str, *, finish_reason: str = "stop") -> MagicMock:
    """Imita lo justo de la respuesta de Groq que usa call_provider()."""
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content), finish_reason=finish_reason)]
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    return response


def _llamar(task: str = "tarea_de_prueba", *, agent_id: str | None = "01",
            agent_name: str | None = "Analista", model: str = "modelo-x") -> str:
    return call_provider(
        system_prompt=PROMPT_SISTEMA, user_message=MENSAJE_USUARIO,
        model=model, max_tokens=100, task=task,
        agent_id=agent_id, agent_name=agent_name,
    )


@pytest.fixture
def groq_falso(monkeypatch):
    """Cliente de Groq simulado: devuelve `RESPUESTA` y no toca la red."""
    monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
    monkeypatch.delenv("NEXUS_MOCK_LLM", raising=False)
    cliente = MagicMock()
    cliente.chat.completions.create.return_value = _fake_response(RESPUESTA)
    with patch("groq.Groq", return_value=cliente):
        yield cliente


# ── Ciclo de vida del grabador ────────────────────────────────────────────────

class TestCicloDeVida:
    def test_sin_grabador_abierto_record_response_no_hace_nada(self):
        recorder.record_response(
            task="x", model="m", agent_id=None, agent_name=None,
            truncated=False, response="texto",
        )
        assert recorder.current() is None  # no crea un grabador implícito

    def test_abrir_activa_y_cerrar_desactiva(self, tmp_path):
        token = recorder.open_recorder()
        assert recorder.current() is not None
        recorder.close_recorder(token, output_path=tmp_path / "g.json")
        assert recorder.current() is None

    def test_las_entradas_quedan_en_orden_con_su_numero_de_secuencia(self, tmp_path):
        token = recorder.open_recorder()
        for tarea in ("a", "b", "c"):
            recorder.record_response(
                task=tarea, model="m", agent_id="01", agent_name="N",
                truncated=False, response=f"r-{tarea}",
            )
        entradas = recorder.close_recorder(token, output_path=tmp_path / "g.json")
        assert [e["task"] for e in entradas] == ["a", "b", "c"]
        assert [e["seq"] for e in entradas] == [1, 2, 3]


# ── Archivo de salida ─────────────────────────────────────────────────────────

class TestArchivo:
    def test_escribe_un_json_utf8_con_las_claves_esperadas(self, tmp_path):
        destino = tmp_path / "sub" / "grabacion.json"
        token = recorder.open_recorder()
        recorder.record_response(
            task="agente01_hipotesis", model="modelo-x", agent_id="01",
            agent_name="Analista de Literatura", truncated=True,
            response="neuropatía axonal — ñandú",
        )
        recorder.close_recorder(token, output_path=destino)

        crudo = destino.read_text(encoding="utf-8")
        assert "neuropatía" in crudo  # ensure_ascii=False
        datos = json.loads(crudo)
        assert set(datos) == {"generated_at", "entries"}
        assert set(datos["entries"][0]) == {
            "seq", "task", "agent_id", "agent_name", "model", "truncated", "response",
        }
        assert datos["entries"][0]["truncated"] is True
        assert datos["entries"][0]["response"] == "neuropatía axonal — ñandú"

    def test_un_fallo_al_escribir_no_levanta_y_avisa_sin_el_texto(self, tmp_path, capsys):
        # La ruta de salida es un directorio existente: abrirla para escribir falla.
        token = recorder.open_recorder()
        recorder.record_response(
            task="x", model="m", agent_id=None, agent_name=None,
            truncated=False, response=RESPUESTA,
        )
        entradas = recorder.close_recorder(token, output_path=tmp_path)
        err = capsys.readouterr().err
        assert entradas is not None and len(entradas) == 1  # se conservan en memoria
        assert "grabador" in err
        assert RESPUESTA not in err


# ── Propagación del contexto ──────────────────────────────────────────────────

class TestPropagacion:
    @pytest.mark.asyncio
    async def test_el_contexto_llega_a_asyncio_to_thread_y_gather(self, tmp_path):
        """Misma primitiva que el orquestador: gather + to_thread."""
        token = recorder.open_recorder()

        def registrar(nombre: str) -> None:
            recorder.record_response(
                task=nombre, model="m", agent_id=None, agent_name=None,
                truncated=False, response=f"r-{nombre}",
            )

        await asyncio.gather(*(asyncio.to_thread(registrar, n) for n in ("a", "b", "c")))
        entradas = recorder.close_recorder(token, output_path=tmp_path / "g.json")
        assert sorted(e["task"] for e in entradas) == ["a", "b", "c"]
        assert sorted(e["seq"] for e in entradas) == [1, 2, 3]  # sin repetidos

    @pytest.mark.asyncio
    async def test_call_provider_graba_desde_to_thread(self, groq_falso, tmp_path):
        token = recorder.open_recorder()
        await asyncio.gather(
            asyncio.to_thread(_llamar, "t1"), asyncio.to_thread(_llamar, "t2"),
        )
        entradas = recorder.close_recorder(token, output_path=tmp_path / "g.json")
        assert sorted(e["task"] for e in entradas) == ["t1", "t2"]


# ── Enganche en call_provider() ───────────────────────────────────────────────

class TestCallProvider:
    def test_sin_grabador_devuelve_lo_mismo_de_siempre(self, groq_falso):
        assert _llamar() == RESPUESTA

    def test_graba_la_respuesta_con_sus_metadatos(self, groq_falso, tmp_path):
        token = recorder.open_recorder()
        devuelto = _llamar("agente01_hipotesis", agent_id="01", agent_name="Analista",
                           model="modelo-x")
        entradas = recorder.close_recorder(token, output_path=tmp_path / "g.json")
        assert devuelto == RESPUESTA
        assert len(entradas) == 1
        e = entradas[0]
        assert (e["task"], e["agent_id"], e["agent_name"], e["model"]) == (
            "agente01_hipotesis", "01", "Analista", "modelo-x",
        )
        assert e["response"] == RESPUESTA
        assert e["truncated"] is False

    def test_marca_la_respuesta_truncada(self, groq_falso, tmp_path):
        groq_falso.chat.completions.create.return_value = _fake_response(
            "corta", finish_reason="length",
        )
        token = recorder.open_recorder()
        _llamar()
        entradas = recorder.close_recorder(token, output_path=tmp_path / "g.json")
        assert entradas[0]["truncated"] is True

    def test_nunca_guarda_el_prompt_ni_el_mensaje_del_usuario(self, groq_falso, tmp_path):
        destino = tmp_path / "g.json"
        token = recorder.open_recorder()
        _llamar()
        recorder.close_recorder(token, output_path=destino)
        contenido = destino.read_text(encoding="utf-8")
        assert PROMPT_SISTEMA not in contenido
        assert MENSAJE_USUARIO not in contenido

    def test_una_llamada_fallida_no_se_graba(self, groq_falso, tmp_path):
        groq_falso.chat.completions.create.side_effect = RuntimeError("falla de red")
        token = recorder.open_recorder()
        with pytest.raises(RuntimeError):
            _llamar()
        entradas = recorder.close_recorder(token, output_path=tmp_path / "g.json")
        assert entradas == []

    def test_en_modo_mock_no_se_graba(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NEXUS_MOCK_LLM", "1")
        token = recorder.open_recorder()
        _llamar("pico_sintesis")
        entradas = recorder.close_recorder(token, output_path=tmp_path / "g.json")
        assert entradas == []

    def test_un_fallo_del_grabador_no_rompe_la_llamada(self, groq_falso, capsys):
        token = recorder.open_recorder()
        try:
            with patch.object(recorder, "record_response",
                              side_effect=RuntimeError(RESPUESTA)):
                devuelto = _llamar()
        finally:
            recorder.close_recorder(token, output_path=os.devnull)
        err = capsys.readouterr().err
        assert devuelto == RESPUESTA
        assert "grabador" in err
        assert RESPUESTA not in err  # el aviso no arrastra el texto de la respuesta

    def test_no_se_activa_por_variable_de_entorno(self, groq_falso, monkeypatch):
        for nombre in ("NEXUS_RECORD", "NEXUS_RECORD_RESPONSES", "NEXUS_GRABAR"):
            monkeypatch.setenv(nombre, "1")
        _llamar()
        assert recorder.current() is None


# ── scripts/medir_costos.py --grabar ──────────────────────────────────────────

def _cargar_script():
    """Importa `scripts/medir_costos.py` como módulo, sin ejecutarlo."""
    ruta = _RAIZ / "scripts" / "medir_costos.py"
    sys.path.insert(0, str(_RAIZ / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location("medir_costos_bajo_test", ruta)
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = modulo  # los dataclasses del script lo exigen
        spec.loader.exec_module(modulo)
    finally:
        sys.path.remove(str(_RAIZ / "scripts"))
    return modulo


class TestScriptGrabar:
    def test_preserva_la_grabacion_previa_con_su_fecha(self, tmp_path):
        script = _cargar_script()
        previa = tmp_path / "grabacion.json"
        previa.write_text('{"previa": true}', encoding="utf-8")
        os.utime(previa, (1_700_000_000, 1_700_000_000))

        script.preservar_grabacion_anterior(tmp_path)

        assert not previa.exists()
        conservadas = list(tmp_path.glob("grabacion.*.json"))
        assert len(conservadas) == 1
        assert json.loads(conservadas[0].read_text(encoding="utf-8")) == {"previa": True}

    def test_sin_grabacion_previa_no_hace_nada(self, tmp_path):
        _cargar_script().preservar_grabacion_anterior(tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_grabar_con_mock_no_escribe_grabacion_y_avisa(self, tmp_path):
        env = {**os.environ, "GROQ_API_KEY": "", "NEXUS_MOCK_LLM": ""}
        r = subprocess.run(
            [sys.executable, str(_RAIZ / "scripts" / "medir_costos.py"),
             "--mock", "--grabar", "--salida", str(tmp_path)],
            capture_output=True, text=True, env=env, cwd=_RAIZ, timeout=300,
        )
        assert r.returncode == 0, r.stderr[-500:]
        assert not (tmp_path / "grabacion.json").exists()
        assert "modo mock" in r.stderr and "grabar" in r.stderr.lower()
