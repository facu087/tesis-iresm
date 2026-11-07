"""
Tests del evaluador de calidad del reporte (backend/pipeline/calidad.py),
tarjeta #59. Caso base: neuropatía axonal sensitivomotora, varón de 42 años.
"""

from __future__ import annotations

import socket
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.api.schemas import (
    ArbitrationOut,
    CaseSummarySection,
    DebateSummary,
    RankedHypothesis,
    RecitationOut,
    ReportMetadata,
    StructuredReport,
    VerificationSummary,
)
from backend.models.hypothesis import Source
from backend.models.trial import ClinicalTrial
from backend.pipeline.calidad import CRITERIOS, Criterios, evaluar

_NARRATIVA = "Paciente varón de 42 años con neuropatía axonal sensitivomotora de dos años de evolución."
_RESUMEN_EJECUTIVO = "Resumen ejecutivo del caso de neuropatía axonal con tres líneas de investigación."


def _hipotesis(
    rank: int,
    *,
    status: str = "respaldada",
    efectivo: str = "III",
    declarado: str | None = "III",
    verificadas: int = 1,
    agentes: list[str] | None = None,
) -> RankedHypothesis:
    return RankedHypothesis(
        rank=rank,
        text=f"Hipótesis número {rank}: neuropatía axonal por causa específica {rank}.",
        priority="MEDIUM",
        evidence_level=efectivo,
        declared_evidence_level=declarado,
        rationale=f"Fundamentación clínica reservada de la hipótesis {rank}.",
        supporting_agents=agentes if agentes is not None else ["Analista de Literatura"],
        sources=[Source(pmid=f"{30000000 + rank}", title=f"Artículo {rank}")],
        status=status,
        verified_sources=verificadas,
    )


def _verificacion(
    *, verificadas: int = 8, discordantes: int = 2, inexistentes: int = 0, estado: str | None = "completa"
) -> VerificationSummary:
    return VerificationSummary(
        total_fuentes=verificadas + discordantes + inexistentes,
        verificadas=verificadas,
        discordantes=discordantes,
        inexistentes=inexistentes,
        estado=estado,
    )


def _reporte(
    hipotesis: list[RankedHypothesis] | None = None,
    *,
    verificacion: VerificationSummary | None = None,
    mock: bool = False,
    disclaimer: str | None = None,
    arbitraje: ArbitrationOut | None = None,
    sin_arbitraje: bool = False,
) -> StructuredReport:
    """Reporte del caso base que, sin argumentos, cumple todos los criterios."""
    metadata = ReportMetadata(
        generated_at=datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc),
        nexus_version="0.5.0",
        processing_time_seconds=480.0,
        mock=mock,
    )
    if disclaimer is not None:
        metadata.disclaimer = disclaimer
    return StructuredReport(
        metadata=metadata,
        case_summary=CaseSummarySection(narrative=_NARRATIVA),
        hypotheses=hipotesis if hipotesis is not None else [_hipotesis(i) for i in range(1, 5)],
        debate_summary=DebateSummary(
            rounds_completed=4, total_critiques=6, divergences=[], consensus_reached=True
        ),
        clinical_trials=[
            ClinicalTrial(
                nct_id="NCT04000001", title="Ensayo", status="RECRUITING",
                brief_summary="Ensayo sobre neuropatía axonal.", url="https://x",
            )
        ],
        bibliography=[],
        verification=verificacion or _verificacion(),
        arbitration=None if sin_arbitraje else (
            arbitraje or ArbitrationOut(
                cited_sources=10, rag_overlap=4, contradictions=1,
                recitation=RecitationOut(executed=True, recited=3, improved=1),
            )
        ),
        executive_summary=_RESUMEN_EJECUTIVO,
    )


def _metrica(evaluacion, nombre: str):
    return next(m for m in evaluacion.metricas if m.nombre == nombre)


# ── Criterios ──────────────────────────────────────────────────────────────────

class TestCriterios:
    def test_umbrales_provisionales_de_la_spec(self):
        assert CRITERIOS.min_cobertura_respaldo == 0.50
        assert CRITERIOS.min_precision_citas == 0.70
        assert CRITERIOS.max_sobredeclaracion == 0.50
        assert CRITERIOS.version

    def test_los_criterios_no_se_pueden_modificar(self):
        with pytest.raises(ValidationError):
            CRITERIOS.min_precision_citas = 0.1  # type: ignore[misc]

    def test_la_evaluacion_declara_sus_criterios(self):
        evaluacion = evaluar(_reporte())
        assert evaluacion.criterios == CRITERIOS
        assert {m.nombre: m.umbral for m in evaluacion.metricas} == {
            "Cobertura de respaldo": 0.50,
            "Precisión de citas": 0.70,
            "Sobredeclaración": 0.50,
        }


# ── Métricas ───────────────────────────────────────────────────────────────────

class TestMetricas:
    def test_cobertura_en_el_umbral_exacto_se_cumple(self):
        hipotesis = [_hipotesis(1), _hipotesis(2),
                     _hipotesis(3, status="especulativa", verificadas=0),
                     _hipotesis(4, status="especulativa", verificadas=0)]
        m = _metrica(evaluar(_reporte(hipotesis)), "Cobertura de respaldo")
        assert m.valor == 0.5
        assert m.cumple

    def test_cobertura_debajo_del_umbral(self):
        hipotesis = [_hipotesis(1)] + [
            _hipotesis(i, status="especulativa", verificadas=0) for i in range(2, 5)
        ]
        evaluacion = evaluar(_reporte(hipotesis))
        m = _metrica(evaluacion, "Cobertura de respaldo")
        assert m.valor == 0.25 and not m.cumple
        assert evaluacion.veredicto == "no_cumple"

    def test_precision_con_citas_inventadas(self):
        evaluacion = evaluar(_reporte(verificacion=_verificacion(verificadas=4, discordantes=5, inexistentes=1)))
        m = _metrica(evaluacion, "Precisión de citas")
        assert m.valor == pytest.approx(0.4)
        assert (m.numerador, m.denominador) == (4, 10)
        assert not m.cumple
        assert "Precisión de citas 0,40 < 0,70." in evaluacion.motivos

    def test_sin_citas_contrastables_queda_sin_datos_y_no_se_cumple(self):
        evaluacion = evaluar(_reporte(verificacion=_verificacion(verificadas=0, discordantes=0)))
        m = _metrica(evaluacion, "Precisión de citas")
        assert m.valor is None and not m.cumple
        assert evaluacion.veredicto == "no_cumple"

    def test_la_comparacion_usa_el_valor_sin_redondear(self):
        # 0,6999... se mostraría como 0,70 pero no llega al umbral.
        m = _metrica(
            evaluar(_reporte(verificacion=_verificacion(verificadas=6999, discordantes=3001))),
            "Precisión de citas",
        )
        assert not m.cumple

    def test_la_precision_usa_las_fuentes_deduplicadas_del_resumen(self):
        # Dos hipótesis citan el mismo PMID: cuenta una sola vez porque la
        # métrica sale de VerificationSummary, no de hypotheses[].sources.
        h1, h2 = _hipotesis(1), _hipotesis(2)
        h2.sources = list(h1.sources)
        m = _metrica(
            evaluar(_reporte([h1, h2], verificacion=_verificacion(verificadas=1, discordantes=0))),
            "Precisión de citas",
        )
        assert (m.numerador, m.denominador) == (1, 1)

    def test_agentes_que_sobredeclaran(self):
        hipotesis = [_hipotesis(i, declarado="I", efectivo="III") for i in range(1, 7)] + [
            _hipotesis(i) for i in range(7, 11)
        ]
        evaluacion = evaluar(_reporte(hipotesis))
        m = _metrica(evaluacion, "Sobredeclaración")
        assert m.valor == pytest.approx(0.6) and not m.cumple
        assert "Sobredeclaración 0,60 > 0,50." in evaluacion.motivos

    def test_sin_nivel_declarado_no_cuenta_como_sobredeclarada(self):
        evaluacion = evaluar(_reporte([_hipotesis(1, declarado=None)]))
        assert not evaluacion.detalle[0].sobredeclarada
        assert _metrica(evaluacion, "Sobredeclaración").valor == 0.0

    def test_sin_hipotesis_las_metricas_por_hipotesis_quedan_sin_datos(self):
        evaluacion = evaluar(_reporte([]))
        assert _metrica(evaluacion, "Cobertura de respaldo").valor is None
        assert _metrica(evaluacion, "Sobredeclaración").valor is None


# ── Evaluabilidad ──────────────────────────────────────────────────────────────

class TestEvaluabilidad:
    def test_reporte_en_modo_mock(self):
        evaluacion = evaluar(_reporte(mock=True))
        assert evaluacion.veredicto == "no_evaluable"
        assert evaluacion.modo_mock
        assert any("modo mock" in m for m in evaluacion.motivos)
        # Las métricas se calculan igual.
        assert all(m.valor is not None for m in evaluacion.metricas)

    @pytest.mark.parametrize("estado", ["no_disponible", "parcial"])
    def test_verificacion_caida(self, estado):
        evaluacion = evaluar(_reporte(verificacion=_verificacion(estado=estado)))
        assert evaluacion.veredicto == "no_evaluable"
        assert any(estado in m for m in evaluacion.motivos)
        assert evaluacion.estado_verificacion == estado

    def test_reporte_anterior_sin_estado_de_verificacion(self):
        evaluacion = evaluar(_reporte(verificacion=_verificacion(estado=None)))
        assert evaluacion.veredicto == "no_evaluable"

    def test_sin_consulta_es_evaluable_y_la_precision_queda_sin_datos(self):
        evaluacion = evaluar(
            _reporte(verificacion=_verificacion(verificadas=0, discordantes=0, estado="sin_consulta"))
        )
        assert evaluacion.veredicto != "no_evaluable"
        assert _metrica(evaluacion, "Precisión de citas").valor is None

    def test_no_evaluable_no_mezcla_motivos_de_metricas(self):
        evaluacion = evaluar(_reporte(mock=True, verificacion=_verificacion(verificadas=1, discordantes=9)))
        assert evaluacion.veredicto == "no_evaluable"
        assert not any("Precisión" in m for m in evaluacion.motivos)


# ── Consistencia ───────────────────────────────────────────────────────────────

class TestConsistencia:
    def test_reporte_sin_hipotesis(self):
        evaluacion = evaluar(_reporte([]))
        assert evaluacion.veredicto == "no_cumple"
        assert "El reporte no tiene hipótesis." in evaluacion.motivos

    def test_nivel_alto_sin_respaldo(self):
        hipotesis = [_hipotesis(1), _hipotesis(2), _hipotesis(3, efectivo="II", declarado="II", verificadas=0)]
        evaluacion = evaluar(_reporte(hipotesis))
        assert evaluacion.veredicto == "no_cumple"
        assert "La hipótesis #3 tiene nivel II sin ninguna fuente verificada." in evaluacion.motivos

    def test_falta_el_aviso_de_no_diagnostico(self):
        evaluacion = evaluar(_reporte(disclaimer="   "))
        assert evaluacion.veredicto == "no_cumple"
        assert "Falta el aviso de que NEXUS no emite diagnósticos." in evaluacion.motivos


# ── Veredicto ──────────────────────────────────────────────────────────────────

class TestVeredicto:
    def test_todo_en_orden(self):
        evaluacion = evaluar(_reporte())
        assert evaluacion.veredicto == "cumple"
        assert evaluacion.motivos == []

    def test_una_metrica_falla(self):
        evaluacion = evaluar(_reporte(verificacion=_verificacion(verificadas=5, discordantes=5)))
        assert evaluacion.veredicto == "no_cumple"
        assert evaluacion.motivos == ["Precisión de citas 0,50 < 0,70."]

    def test_mismo_reporte_mismo_resultado(self):
        reporte = _reporte()
        assert evaluar(reporte).model_dump() == evaluar(reporte).model_dump()

    def test_otros_criterios_cambian_el_veredicto(self):
        exigentes = Criterios(
            version="prueba", min_cobertura_respaldo=1.0, min_precision_citas=0.9, max_sobredeclaracion=0.0
        )
        evaluacion = evaluar(_reporte(), exigentes)
        assert evaluacion.veredicto == "no_cumple"
        assert evaluacion.criterios.version == "prueba"

    def test_sin_red(self, monkeypatch):
        def _prohibido(*args, **kwargs):
            raise AssertionError("la evaluación no puede abrir conexiones")

        monkeypatch.setattr(socket, "create_connection", _prohibido)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        assert evaluar(_reporte()).veredicto == "cumple"


# ── Indicadores ────────────────────────────────────────────────────────────────

class TestIndicadores:
    def test_indicadores_del_reporte_completo(self):
        hipotesis = [
            _hipotesis(1, efectivo="II", declarado="II", agentes=["Analista de Literatura", "Consultor Clínico"]),
            _hipotesis(2, agentes=["Consultor Clínico"]),
            _hipotesis(3, status="pendiente", verificadas=0),
            _hipotesis(4, status="especulativa", verificadas=0),
        ]
        ind = evaluar(_reporte(hipotesis)).indicadores
        assert ind.niveles_efectivos == {"I": 0, "II": 1, "III": 3}
        assert (ind.hipotesis_respaldadas, ind.hipotesis_pendientes, ind.hipotesis_especulativas) == (2, 1, 1)
        assert ind.anclaje_rag == pytest.approx(0.4)
        assert (ind.recitacion_ejecutada, ind.recitacion_hipotesis, ind.recitacion_mejoradas) == (True, 3, 1)
        assert ind.contradicciones == 1
        assert ind.agentes_con_hipotesis == ["Analista de Literatura", "Consultor Clínico"]
        assert ind.ensayos_clinicos == 1

    def test_reporte_sin_arbitraje(self):
        evaluacion = evaluar(_reporte(sin_arbitraje=True))
        ind = evaluacion.indicadores
        assert ind.anclaje_rag is None
        assert ind.citas_ancladas_en_rag is None
        assert ind.recitacion_ejecutada is None
        assert ind.contradicciones is None
        # No disponible no es lo mismo que cero, y no cambia el veredicto.
        assert evaluacion.veredicto == "cumple"


    def test_citas_descartadas_por_no_venir_del_rag(self):
        base = evaluar(_reporte())
        verificacion = _verificacion()
        verificacion.fuera_del_rag = 23
        evaluacion = evaluar(_reporte(verificacion=verificacion))
        assert evaluacion.indicadores.citas_fuera_del_rag == 23
        assert evaluacion.veredicto == base.veredicto
        assert evaluacion.motivos == base.motivos

    def test_reporte_anterior_sin_el_conteo(self):
        assert _verificacion().fuera_del_rag is None
        assert evaluar(_reporte()).indicadores.citas_fuera_del_rag is None


# ── Privacidad ─────────────────────────────────────────────────────────────────

class TestSinTextoClinico:
    def test_la_evaluacion_no_contiene_texto_del_reporte(self):
        reporte = _reporte()
        serializada = evaluar(reporte).model_dump_json()
        for h in reporte.hypotheses:
            assert h.text not in serializada
            assert h.rationale not in serializada
        assert _NARRATIVA not in serializada
        assert _RESUMEN_EJECUTIVO not in serializada

    def test_el_detalle_identifica_por_posicion(self):
        detalle = evaluar(_reporte()).detalle
        assert [d.rank for d in detalle] == [1, 2, 3, 4]
        assert set(detalle[0].model_dump()) == {
            "rank", "status", "nivel_declarado", "nivel_efectivo", "fuentes_verificadas", "sobredeclarada",
        }
