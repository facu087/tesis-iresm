"""
Tests de scripts/evaluar_reporte.py (tarjeta #59): lee un reporte guardado,
imprime la evaluación, la guarda y sale con un código según el veredicto.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from tests.test_calidad import _reporte, _verificacion

_RUTA = Path(__file__).parent.parent / "scripts" / "evaluar_reporte.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("evaluar_reporte_bajo_test", _RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _guardar(carpeta: Path, nombre: str, contenido: str) -> Path:
    ruta = carpeta / nombre
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_reporte_que_cumple(script, tmp_path, capsys):
    entrada = _guardar(tmp_path, "corrida.json", _reporte().model_dump_json())
    salida = tmp_path / "salida"

    codigo = script.main([str(entrada)], salida=salida)

    assert codigo == 0
    impreso = capsys.readouterr().out
    assert "VEREDICTO: CUMPLE" in impreso
    guardada = json.loads((salida / "corrida" / "evaluacion.json").read_text(encoding="utf-8"))
    assert guardada["veredicto"] == "cumple"
    assert "VEREDICTO: CUMPLE" in (salida / "corrida" / "evaluacion.txt").read_text(encoding="utf-8")


def test_reporte_que_no_cumple(script, tmp_path, capsys):
    reporte = _reporte(verificacion=_verificacion(verificadas=2, discordantes=8))
    entrada = _guardar(tmp_path, "corrida.json", reporte.model_dump_json())

    assert script.main([str(entrada)], salida=tmp_path / "salida") == 1
    assert "Precisión de citas 0,20 < 0,70." in capsys.readouterr().out


def test_reporte_de_modo_mock_no_es_evaluable(script, tmp_path, capsys):
    entrada = _guardar(tmp_path, "mock.json", _reporte(mock=True).model_dump_json())

    assert script.main([str(entrada)], salida=tmp_path / "salida") == 2
    assert "NO_EVALUABLE" in capsys.readouterr().out


@pytest.mark.parametrize("caso", ["inexistente", "no_json", "no_reporte"])
def test_archivo_invalido(script, tmp_path, capsys, caso):
    if caso == "inexistente":
        entrada = tmp_path / "no_existe.json"
    elif caso == "no_json":
        entrada = _guardar(tmp_path, "roto.json", "{esto no es json")
    else:
        entrada = _guardar(tmp_path, "otro.json", json.dumps({"hola": "mundo"}))
    salida = tmp_path / "salida"

    codigo = script.main([str(entrada)], salida=salida)

    assert codigo == 3
    error = capsys.readouterr().err
    assert error.startswith("Error: ")
    assert not salida.exists()


def test_la_salida_no_contiene_texto_clinico(script, tmp_path, capsys):
    reporte = _reporte()
    entrada = _guardar(tmp_path, "corrida.json", reporte.model_dump_json())
    salida = tmp_path / "salida"

    script.main([str(entrada)], salida=salida)

    textos = [
        capsys.readouterr().out,
        (salida / "corrida" / "evaluacion.json").read_text(encoding="utf-8"),
        (salida / "corrida" / "evaluacion.txt").read_text(encoding="utf-8"),
    ]
    for texto in textos:
        for h in reporte.hypotheses:
            assert h.text not in texto
        assert reporte.case_summary.narrative not in texto


# ── scripts/medir_costos.py guarda el reporte que se evalúa ──────────────────

def test_medir_costos_guarda_un_reporte_evaluable_sin_pisar_el_anterior(script, tmp_path, capsys):
    from tests.test_recorder import _cargar_script

    medir_costos = _cargar_script()
    primero, segundo = _reporte(), _reporte(mock=True)

    ruta = medir_costos.guardar_reporte(tmp_path, primero)
    medir_costos.guardar_reporte(tmp_path, segundo)

    assert ruta == tmp_path / "reporte.json"
    rotados = list(tmp_path.glob("reporte.*.json"))
    assert len(rotados) == 1
    assert json.loads(rotados[0].read_text(encoding="utf-8"))["metadata"]["mock"] is False
    assert not list(tmp_path.glob("*.tmp"))
    # El que quedó en reporte.json es el último y el evaluador lo lee.
    assert script.main([str(ruta)], salida=tmp_path / "salida") == 2


def test_la_salida_muestra_las_citas_fuera_del_rag(script, tmp_path, capsys):
    verificacion = _verificacion()
    verificacion.fuera_del_rag = 23
    entrada = _guardar(tmp_path, "nuevo.json", _reporte(verificacion=verificacion).model_dump_json())
    script.main([str(entrada)], salida=tmp_path / "salida")
    assert "Citas fuera del RAG (descartadas): 23" in capsys.readouterr().out

    anterior = _guardar(tmp_path, "anterior.json", _reporte().model_dump_json())
    script.main([str(anterior)], salida=tmp_path / "salida")
    assert "Citas fuera del RAG (descartadas): no disponible" in capsys.readouterr().out
