"""
Tests de scripts/revision_medica.py (tarjeta #60): `preparar` arma el material
de la sesión desde un reporte guardado y `tabular` resume la planilla respondida.
"""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from tests.test_calidad import _hipotesis, _reporte

_RUTA = Path(__file__).parent.parent / "scripts" / "revision_medica.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("revision_medica_bajo_test", _RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _guardar_reporte(carpeta: Path, mock: bool = False) -> Path:
    h2 = _hipotesis(2, status="especulativa", verificadas=0)
    h2.sources = []
    ruta = carpeta / "corrida.json"
    ruta.write_text(_reporte([_hipotesis(1), h2], mock=mock).model_dump_json(), encoding="utf-8")
    return ruta


def _leer(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _escribir(ruta: Path, filas: list[dict], delimitador: str = ",") -> None:
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]), delimiter=delimitador)
        escritor.writeheader()
        escritor.writerows(filas)


def _preparar(script, tmp_path) -> Path:
    salida = tmp_path / "material"
    assert script.main(["preparar", str(_guardar_reporte(tmp_path)), "--salida", str(salida)]) == 0
    return salida


def _responder(salida: Path, delimitador: str = ",") -> None:
    filas = _leer(salida / "planilla.csv")
    for fila in filas:
        fila.update(pertinente="Sí", nivel_razonable="si", investigaria="si",
                    cita_respalda="sin_cita" if not fila["citas"] else "no",
                    observaciones="Texto clínico del médico que no debe copiarse")
    _escribir(salida / "planilla.csv", filas, delimitador)
    generales = _leer(salida / "generales.csv")
    for fila in generales:
        fila["respuesta"] = {"falta_hipotesis": "no", "utilidad": "quizás", "claridad": "si"}.get(
            fila["pregunta"], "Comentario libre del médico")
    _escribir(salida / "generales.csv", generales, delimitador)


class TestPreparar:
    def test_genera_el_material(self, script, tmp_path):
        salida = _preparar(script, tmp_path)
        assert (salida / "reporte.pdf").read_bytes().startswith(b"%PDF")
        assert (salida / "planilla.pdf").read_bytes().startswith(b"%PDF")
        filas = _leer(salida / "planilla.csv")
        assert [f["rank"] for f in filas] == ["1", "2"]
        assert filas[0]["pertinente"] == ""
        generales = _leer(salida / "generales.csv")
        assert [g["pregunta"] for g in generales] == [
            "falta_hipotesis", "utilidad", "claridad", "comentarios"]

    def test_no_pisa_una_planilla_existente(self, script, tmp_path, capsys):
        salida = _preparar(script, tmp_path)
        (salida / "planilla.csv").write_text("respuestas del médico", encoding="utf-8")
        codigo = script.main(["preparar", str(tmp_path / "corrida.json"), "--salida", str(salida)])
        assert codigo == 4
        assert (salida / "planilla.csv").read_text(encoding="utf-8") == "respuestas del médico"
        assert "ya existe" in capsys.readouterr().err

    def test_rechaza_un_reporte_de_modo_mock(self, script, tmp_path, capsys):
        ruta = _guardar_reporte(tmp_path, mock=True)
        assert script.main(["preparar", str(ruta), "--salida", str(tmp_path / "m")]) == 2
        assert "modo mock" in capsys.readouterr().err
        assert not (tmp_path / "m").exists()

    def test_archivo_invalido(self, script, tmp_path):
        ruta = tmp_path / "x.json"
        ruta.write_text("{}", encoding="utf-8")
        assert script.main(["preparar", str(ruta), "--salida", str(tmp_path / "m")]) == 3


class TestTabular:
    def test_planilla_respondida(self, script, tmp_path, capsys):
        salida = _preparar(script, tmp_path)
        _responder(salida)
        capsys.readouterr()

        assert script.main(["tabular", str(salida)]) == 0
        impreso = capsys.readouterr().out
        assert "Planilla completa" in impreso
        assert "Pertinencia: 1,00 (2 de 2)" in impreso
        assert "respaldo verificado sin respaldo clínico: 1" in impreso
        resumen = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))
        assert resumen["completa"] is True
        assert resumen["globales"]["utilidad"] == "quizas"

    def test_acepta_punto_y_coma(self, script, tmp_path):
        """LibreOffice o Excel en español guardan el CSV con ';'."""
        salida = _preparar(script, tmp_path)
        _responder(salida, delimitador=";")
        assert script.main(["tabular", str(salida)]) == 0

    def test_incompleta_sale_con_1_y_lista_los_problemas(self, script, tmp_path, capsys):
        salida = _preparar(script, tmp_path)
        assert script.main(["tabular", str(salida)]) == 1
        impreso = capsys.readouterr().out
        assert "Hipótesis 1, pertinente sin responder." in impreso

    def test_falta_la_planilla(self, script, tmp_path):
        assert script.main(["tabular", str(tmp_path / "nada")]) == 3

    def test_el_resumen_no_copia_texto_clinico(self, script, tmp_path, capsys):
        salida = _preparar(script, tmp_path)
        _responder(salida)
        script.main(["tabular", str(salida)])
        impreso = capsys.readouterr().out
        guardado = (salida / "resumen.json").read_text(encoding="utf-8") + (
            salida / "resumen.txt").read_text(encoding="utf-8")
        for texto in ("neuropatía axonal por causa específica", "Texto clínico del médico",
                      "Comentario libre del médico"):
            assert texto not in impreso
            assert texto not in guardado
