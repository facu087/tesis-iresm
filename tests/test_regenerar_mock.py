"""
Tests del generador de `grabadas.json` (`backend/mock/regenerar.py`) y de su
entrada por línea de comandos (`scripts/regenerar_mock.py`).

El generador convierte el `grabacion.json` que deja
`scripts/medir_costos.py --grabar` en un archivo de respuestas del modo mock con
todas las grabaciones de cada tarea. Cubre:
  - conserva todas las entradas, agrupadas por tarea y ordenadas por `seq`;
  - el resultado se carga con el cargador real y reproduce la corrida;
  - el texto de cada respuesta queda sin retocar;
  - rechaza una grabación mal formada y no escribe nada;
  - el script escribe solo en la ruta que recibe.

Todas las grabaciones son sintéticas y temporales: ningún test toca
`backend/mock/grabadas.json`, llama a un LLM ni usa la red.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from backend.mock import regenerar
from backend.mock import responses as mock_responses

_RAIZ = Path(__file__).parent.parent
_VERSIONADO = Path(mock_responses.__file__).with_name("grabadas.json")


def _entrada(seq: int, task: str, agent_id: str | None, response: str,
             *, model: str = "openai/gpt-oss-120b", truncated: bool = False) -> dict:
    """Una entrada con la forma que escribe `recorder.close_recorder()`."""
    return {
        "seq": seq, "task": task, "agent_id": agent_id,
        "agent_name": f"Agente {agent_id}" if agent_id else None,
        "model": model, "truncated": truncated, "response": response,
    }


def _grabacion() -> dict:
    """Una corrida corta, con las entradas fuera de orden a propósito."""
    return {
        "generated_at": "2026-10-06T14:03:11.123456+00:00",
        "entries": [
            _entrada(5, "debate_revision", "01", '{\n  "ronda": 4\n}'),
            _entrada(1, "pico_sintesis", None, '{"pico": "síntesis — ñandú"}'),
            _entrada(3, "debate_revision", "01", '{\n  "ronda": 3\n}'),
            _entrada(2, "debate_critica", "01", '{"critiques": []}'),
            _entrada(4, "debate_revision", "02", '{"ronda": 3, "agente": "02"}'),
        ],
    }


@pytest.fixture
def cargador(monkeypatch):
    """Apunta el cargador real a un archivo y descarta la caché al terminar."""
    def apuntar(ruta: Path) -> None:
        monkeypatch.setattr(mock_responses, "_ARCHIVO_GRABADAS", ruta)
        monkeypatch.setattr(mock_responses, "_CACHE", None)

    return apuntar


# ── Conversión ────────────────────────────────────────────────────────────────

class TestConversion:
    def test_conserva_todas_las_entradas_agrupadas_por_tarea(self):
        datos = regenerar.construir_grabadas(_grabacion())
        assert set(datos["tasks"]) == {"pico_sintesis", "debate_critica", "debate_revision"}
        assert sum(len(entradas) for entradas in datos["tasks"].values()) == 5

    def test_ordena_las_entradas_de_cada_tarea_por_seq(self):
        datos = regenerar.construir_grabadas(_grabacion())
        assert [e["seq"] for e in datos["tasks"]["debate_revision"]] == [3, 4, 5]
        assert [e["agent_id"] for e in datos["tasks"]["debate_revision"]] == ["01", "02", "01"]

    def test_las_tareas_quedan_en_orden_alfabetico(self):
        datos = regenerar.construir_grabadas(_grabacion())
        assert list(datos["tasks"]) == sorted(datos["tasks"])

    def test_cada_entrada_trae_los_campos_del_archivo_de_datos(self):
        datos = regenerar.construir_grabadas(_grabacion())
        for entradas in datos["tasks"].values():
            for entrada in entradas:
                assert set(entrada) == {"agent_id", "model", "seq", "recorded_at", "response"}
                assert entrada["recorded_at"] == "2026-10-06"
        assert datos["recorded_at"] == "2026-10-06"
        assert datos["tasks"]["pico_sintesis"][0]["agent_id"] is None

    def test_la_respuesta_queda_sin_retocar(self):
        datos = regenerar.construir_grabadas(_grabacion())
        assert datos["tasks"]["debate_revision"][0]["response"] == '{\n  "ronda": 3\n}'

    def test_no_modifica_la_grabacion_recibida(self):
        grabacion = _grabacion()
        original = copy.deepcopy(grabacion)
        regenerar.construir_grabadas(grabacion)
        assert grabacion == original

    def test_la_fecha_se_puede_indicar_si_la_grabacion_no_la_trae(self):
        grabacion = _grabacion()
        del grabacion["generated_at"]
        datos = regenerar.construir_grabadas(grabacion, recorded_at="2026-11-02")
        assert datos["recorded_at"] == "2026-11-02"


# ── Ida y vuelta por el cargador real ─────────────────────────────────────────

class TestIdaYVuelta:
    def test_el_archivo_generado_se_carga_y_reproduce_la_corrida(self, tmp_path, cargador):
        origen = tmp_path / "grabacion.json"
        destino = tmp_path / "salida" / "grabadas.json"
        origen.write_text(json.dumps(_grabacion(), ensure_ascii=False), encoding="utf-8")

        resumen = regenerar.regenerar_archivo(origen, destino)
        assert resumen == {"tasks": 3, "entries": 5, "truncated": 0}

        cargador(destino)
        todas = mock_responses.get_recorded_entries()
        assert {t: [e["seq"] for e in es] for t, es in todas.items()} == {
            "debate_critica": [2], "debate_revision": [3, 4, 5], "pico_sintesis": [1],
        }
        token = mock_responses.open_replay_session()
        try:
            assert mock_responses.get_mock_response("pico_sintesis") == (
                '{"pico": "síntesis — ñandú"}'
            )
            revisiones = [
                mock_responses.get_mock_response("debate_revision", agent_id=agente)
                for agente in ("01", "02", "01")
            ]
        finally:
            mock_responses.close_replay_session(token)
        assert revisiones == [
            '{\n  "ronda": 3\n}', '{"ronda": 3, "agente": "02"}', '{\n  "ronda": 4\n}',
        ]

    def test_el_archivo_generado_es_utf8_sin_escapes(self, tmp_path):
        origen = tmp_path / "grabacion.json"
        destino = tmp_path / "grabadas.json"
        origen.write_text(json.dumps(_grabacion(), ensure_ascii=False), encoding="utf-8")
        regenerar.regenerar_archivo(origen, destino)
        crudo = destino.read_text(encoding="utf-8")
        assert "ñandú" in crudo and "\\u" not in crudo

    def test_cuenta_las_respuestas_cortadas(self, tmp_path):
        grabacion = _grabacion()
        grabacion["entries"][0]["truncated"] = True
        origen = tmp_path / "grabacion.json"
        origen.write_text(json.dumps(grabacion), encoding="utf-8")
        resumen = regenerar.regenerar_archivo(origen, tmp_path / "grabadas.json")
        assert resumen["truncated"] == 1


# ── Entrada inválida ──────────────────────────────────────────────────────────

def _sin(campo: str) -> dict:
    grabacion = _grabacion()
    del grabacion["entries"][0][campo]
    return grabacion


def _con(campo: str, valor: object) -> dict:
    grabacion = _grabacion()
    grabacion["entries"][0][campo] = valor
    return grabacion


_INVALIDAS = {
    "no es un objeto": [],
    "sin entries": {"generated_at": "2026-10-06T00:00:00+00:00"},
    "entries no es lista": {"generated_at": "2026-10-06T00:00:00+00:00", "entries": {}},
    "entries vacía": {"generated_at": "2026-10-06T00:00:00+00:00", "entries": []},
    "entrada que no es objeto": {"generated_at": "2026-10-06T00:00:00+00:00",
                                 "entries": ["texto"]},
    "sin task": _sin("task"),
    "task vacía": _con("task", "  "),
    "sin seq": _sin("seq"),
    "seq no entero": _con("seq", "5"),
    "seq booleano": _con("seq", True),
    "seq repetido": _con("seq", 1),
    "sin response": _sin("response"),
    "response vacía": _con("response", "   "),
    "response no texto": _con("response", 3),
    "sin model": _sin("model"),
    "model no texto": _con("model", None),
    "sin agent_id": _sin("agent_id"),
    "agent_id no texto": _con("agent_id", 1),
    "sin fecha": {"entries": _grabacion()["entries"]},
    "fecha ilegible": {**_grabacion(), "generated_at": "ayer"},
}


class TestEntradaInvalida:
    @pytest.mark.parametrize("grabacion", _INVALIDAS.values(), ids=_INVALIDAS.keys())
    def test_rechaza_una_grabacion_mal_formada(self, grabacion):
        with pytest.raises(regenerar.GrabacionInvalida):
            regenerar.construir_grabadas(grabacion)

    def test_el_error_no_contiene_texto_de_respuestas(self):
        grabacion = _con("seq", "5")
        grabacion["entries"][0]["response"] = "SECRETO-CLINICO"
        with pytest.raises(regenerar.GrabacionInvalida) as e:
            regenerar.construir_grabadas(grabacion)
        assert "SECRETO-CLINICO" not in str(e.value)

    @pytest.mark.parametrize("contenido", ["{ esto no es json", json.dumps(_sin("seq"))])
    def test_una_entrada_invalida_no_escribe_el_archivo(self, tmp_path, contenido):
        origen = tmp_path / "grabacion.json"
        destino = tmp_path / "grabadas.json"
        origen.write_text(contenido, encoding="utf-8")
        with pytest.raises(regenerar.GrabacionInvalida):
            regenerar.regenerar_archivo(origen, destino)
        assert not destino.exists()

    def test_un_archivo_de_entrada_ausente_falla_con_el_error_claro(self, tmp_path):
        with pytest.raises(regenerar.GrabacionInvalida):
            regenerar.regenerar_archivo(tmp_path / "no_existe.json", tmp_path / "g.json")

    def test_no_escribe_lo_que_el_cargador_rechazaria(self, tmp_path, monkeypatch):
        """La última palabra la tiene la validación del cargador, no la del generador."""
        origen = tmp_path / "grabacion.json"
        destino = tmp_path / "grabadas.json"
        origen.write_text(json.dumps(_grabacion()), encoding="utf-8")
        destino.write_text("contenido previo", encoding="utf-8")

        def rechazar(datos: object, nombre: str) -> dict:
            raise mock_responses.RespuestasGrabadasInvalidas("rechazado por el cargador")

        monkeypatch.setattr(mock_responses, "validar_grabadas", rechazar)
        with pytest.raises(mock_responses.RespuestasGrabadasInvalidas):
            regenerar.regenerar_archivo(origen, destino)
        assert destino.read_text(encoding="utf-8") == "contenido previo"


# ── scripts/regenerar_mock.py ─────────────────────────────────────────────────

class TestEscrituraDelDestino:
    """
    El destino habitual es el archivo versionado de respuestas: una escritura
    que falla no puede dejarlo truncado ni terminar en un traceback crudo.
    """

    def _origen(self, tmp_path: Path) -> Path:
        origen = tmp_path / "grabacion.json"
        origen.write_text(json.dumps(_grabacion()), encoding="utf-8")
        return origen

    def test_un_fallo_al_reemplazar_deja_el_destino_como_estaba(self, tmp_path, monkeypatch):
        destino = tmp_path / "grabadas.json"
        destino.write_text("contenido anterior", encoding="utf-8")

        def _falla(*_args, **_kwargs):
            raise PermissionError("destino bloqueado")

        monkeypatch.setattr(regenerar.os, "replace", _falla)

        with pytest.raises(regenerar.DestinoNoEscribible):
            regenerar.regenerar_archivo(self._origen(tmp_path), destino)

        assert destino.read_text(encoding="utf-8") == "contenido anterior"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["grabacion.json", "grabadas.json"]

    def test_un_destino_que_es_una_carpeta_falla_con_el_error_claro(self, tmp_path):
        destino = tmp_path / "carpeta"
        destino.mkdir()

        with pytest.raises(regenerar.DestinoNoEscribible):
            regenerar.regenerar_archivo(self._origen(tmp_path), destino)

        assert destino.is_dir()

    def test_el_script_informa_el_fallo_de_escritura_sin_traceback(self, tmp_path, capsys):
        destino = tmp_path / "carpeta"
        destino.mkdir()
        script = _cargar_script()

        codigo = script.main([str(self._origen(tmp_path)), str(destino)])

        assert codigo == 2
        assert "No se escribió ningún archivo" in capsys.readouterr().err


def _cargar_script():
    """Importa `scripts/regenerar_mock.py` como módulo, sin ejecutarlo."""
    ruta = _RAIZ / "scripts" / "regenerar_mock.py"
    spec = importlib.util.spec_from_file_location("regenerar_mock_bajo_test", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class TestScript:
    def test_escribe_en_la_ruta_indicada_y_no_toca_el_archivo_versionado(
        self, tmp_path, capsys
    ):
        antes = _VERSIONADO.read_bytes()
        origen = tmp_path / "grabacion.json"
        destino = tmp_path / "grabadas.json"
        origen.write_text(json.dumps(_grabacion(), ensure_ascii=False), encoding="utf-8")

        codigo = _cargar_script().main([str(origen), str(destino)])

        assert codigo == 0
        assert set(json.loads(destino.read_text(encoding="utf-8"))["tasks"]) == {
            "pico_sintesis", "debate_critica", "debate_revision",
        }
        assert _VERSIONADO.read_bytes() == antes
        assert "5 respuesta(s)" in capsys.readouterr().err

    def test_exige_las_dos_rutas(self, tmp_path):
        """Sin ruta de salida no hay un destino por defecto que pisar."""
        with pytest.raises(SystemExit) as e:
            _cargar_script().main([str(tmp_path / "grabacion.json")])
        assert e.value.code == 2

    def test_una_grabacion_invalida_devuelve_error_y_no_escribe(self, tmp_path, capsys):
        origen = tmp_path / "grabacion.json"
        destino = tmp_path / "grabadas.json"
        grabacion = _sin("seq")
        grabacion["entries"][1]["response"] = "SECRETO-CLINICO"
        origen.write_text(json.dumps(grabacion), encoding="utf-8")

        codigo = _cargar_script().main([str(origen), str(destino)])

        assert codigo == 2
        assert not destino.exists()
        err = capsys.readouterr().err
        assert "ERROR" in err and "SECRETO-CLINICO" not in err

    def test_avisa_si_hay_respuestas_cortadas(self, tmp_path, capsys):
        grabacion = _grabacion()
        grabacion["entries"][0]["truncated"] = True
        origen = tmp_path / "grabacion.json"
        origen.write_text(json.dumps(grabacion), encoding="utf-8")
        assert _cargar_script().main([str(origen), str(tmp_path / "g.json")]) == 0
        assert "cortada" in capsys.readouterr().err
