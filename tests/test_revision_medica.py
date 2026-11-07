"""
Tests de backend/pipeline/revision_medica.py (tarjeta #60): la planilla que
completa el médico sobre un reporte de NEXUS y la tabulación de sus respuestas.

Caso base: neuropatía axonal sensitivomotora, varón de 42 años.
"""

from __future__ import annotations

import pytest

from backend.models.hypothesis import Source
from backend.pipeline.revision_medica import (
    COLUMNAS_PLANILLA,
    PREGUNTAS_GLOBALES,
    PREGUNTAS_HIPOTESIS,
    filas_planilla,
    generar_planilla_pdf,
    tabular,
)
from tests.test_calidad import _hipotesis, _reporte


def _reporte_base():
    h1 = _hipotesis(1)
    h1.sources = [Source(pmid="29972757", title="Titulo citado", actual_title="Patisiran for hATTR")]
    h2 = _hipotesis(2, status="especulativa", verificadas=0)
    h2.sources = []
    h3 = _hipotesis(3)
    return _reporte([h1, h2, h3])


def _respuestas(por_rank: dict):
    """Filas de la planilla con respuestas: rank -> dict de respuestas."""
    filas = filas_planilla(_reporte_base())
    for fila in filas:
        fila.update(por_rank.get(fila["rank"], {}))
    return filas


def _completa(pertinente="si", cita="si", nivel="si", investigaria="si"):
    return {"pertinente": pertinente, "cita_respalda": cita,
            "nivel_razonable": nivel, "investigaria": investigaria}


def _globales(**respuestas):
    base = {"falta_hipotesis": "no", "utilidad": "si", "claridad": "si"}
    base.update(respuestas)
    return [{"pregunta": p.id, "respuesta": base.get(p.id, "")} for p in PREGUNTAS_GLOBALES]


# ── Planilla ───────────────────────────────────────────────────────────────────

class TestFilasPlanilla:
    def test_una_fila_por_hipotesis_en_el_orden_del_reporte(self):
        filas = filas_planilla(_reporte_base())
        assert [f["rank"] for f in filas] == [1, 2, 3]
        assert set(filas[0]) == set(COLUMNAS_PLANILLA)

    def test_la_cita_muestra_el_titulo_real_de_pubmed(self):
        filas = filas_planilla(_reporte_base())
        assert filas[0]["citas"] == "PMID 29972757: Patisiran for hATTR"

    def test_sin_citas_lo_dice(self):
        assert filas_planilla(_reporte_base())[1]["citas"] == ""

    def test_trae_nivel_y_estado_del_reporte_y_respuestas_vacias(self):
        fila = filas_planilla(_reporte_base())[1]
        assert (fila["nivel"], fila["estado"]) == ("III", "especulativa")
        for pregunta in PREGUNTAS_HIPOTESIS:
            assert fila[pregunta.id] == ""

    def test_pdf_de_la_planilla(self):
        pdf = generar_planilla_pdf(_reporte_base())
        assert pdf.startswith(b"%PDF")


# ── Tabulación ─────────────────────────────────────────────────────────────────

class TestTabular:
    def test_planilla_completa(self):
        filas = _respuestas({1: _completa(), 2: _completa(cita="sin_cita", investigaria="no"),
                               3: _completa(pertinente="parcial", cita="no", nivel="sobreestimado")})
        resumen = tabular(filas, _globales())
        assert resumen.completa
        assert resumen.conteos["pertinente"] == {"si": 2, "parcial": 1, "no": 0}
        assert resumen.indicadores["pertinencia"] == pytest.approx(2 / 3)
        # sin_cita no cuenta en el denominador del respaldo de las citas
        assert resumen.indicadores["citas_que_respaldan"] == pytest.approx(1 / 2)
        assert resumen.indicadores["nivel_razonable"] == pytest.approx(2 / 3)
        assert resumen.indicadores["investigaria"] == pytest.approx(2 / 3)

    def test_respaldo_verificado_que_el_medico_no_comparte(self):
        """La verificación confirma el PMID, no que el artículo respalde la hipótesis."""
        filas = _respuestas({1: _completa(cita="no"), 2: _completa(cita="sin_cita"),
                               3: _completa(cita="parcial")})
        resumen = tabular(filas, _globales())
        assert resumen.respaldo_verificado_sin_respaldo_clinico == [1]

    def test_normaliza_tildes_y_mayusculas(self):
        filas = _respuestas({1: _completa(pertinente=" Sí "), 2: _completa(cita="Sin cita"),
                               3: _completa()})
        resumen = tabular(filas, _globales(utilidad="Quizás"))
        assert resumen.completa
        assert resumen.conteos["pertinente"]["si"] == 3
        assert resumen.globales["utilidad"] == "quizas"

    def test_respuesta_fuera_de_las_opciones(self):
        filas = _respuestas({1: _completa(pertinente="tal vez"), 2: _completa(cita="sin_cita"),
                               3: _completa()})
        resumen = tabular(filas, _globales())
        assert not resumen.completa
        assert "Hipótesis 1, pertinente: \"tal vez\" no es una opción (si, parcial, no)." in resumen.problemas

    def test_sin_responder(self):
        filas = _respuestas({1: _completa(), 3: _completa()})
        resumen = tabular(filas, _globales(claridad=""))
        assert not resumen.completa
        assert resumen.sin_responder["pertinente"] == 1
        assert "Pregunta general claridad sin responder." in resumen.problemas

    def test_sin_cita_en_una_hipotesis_con_citas_es_inconsistente(self):
        filas = _respuestas({1: _completa(cita="sin_cita"), 2: _completa(cita="si"), 3: _completa()})
        resumen = tabular(filas, _globales())
        assert not resumen.completa
        assert "Hipótesis 1: tiene citas pero se respondió sin_cita." in resumen.problemas
        assert "Hipótesis 2: no tiene citas; la respuesta debe ser sin_cita." in resumen.problemas

    def test_planilla_vacia_no_divide_por_cero(self):
        resumen = tabular([], _globales())
        assert resumen.indicadores["pertinencia"] is None
        assert not resumen.completa
