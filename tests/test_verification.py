"""
Tests de la verificación bibliográfica (backend/pipeline/verification.py).

Ningún test llama a PubMed: el cliente se reemplaza por un doble que devuelve
metadatos fijos. El caso central es el que motivó el módulo — un PMID que
existe pero corresponde a otro artículo (alucinación típica de un LLM).
"""

import pytest

from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import Report
from backend.pipeline import verification
from backend.pipeline.report_builder import build_export
from backend.pipeline.verification import (
    SourceStatus,
    _title_match_score,
    _verify_one,
    verify_report_sources,
)

from .test_report_builder import _make_case, _make_report


# ── Doble de prueba del cliente PubMed ─────────────────────────────────────────

class _FakePubMedClient:
    """Reemplaza a PubMedClient devolviendo metadatos fijos, sin red."""

    metadata: dict[str, dict] = {}
    error: Exception | None = None

    async def __aenter__(self) -> "_FakePubMedClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def fetch_metadata(self, pmids: list[str]) -> dict[str, dict]:
        if _FakePubMedClient.error is not None:
            raise _FakePubMedClient.error
        return {p: _FakePubMedClient.metadata[p] for p in pmids if p in _FakePubMedClient.metadata}


@pytest.fixture(autouse=True)
def _fake_pubmed(monkeypatch):
    """Instala el doble y limpia su estado entre tests."""
    _FakePubMedClient.metadata = {}
    _FakePubMedClient.error = None
    monkeypatch.setattr(verification, "PubMedClient", _FakePubMedClient)
    return _FakePubMedClient


def _source(pmid: str | None, title: str) -> Source:
    return Source(pmid=pmid, title=title)


def _hypothesis_con(sources: list[Source], text: str = "Hipótesis.") -> Hypothesis:
    return Hypothesis(
        text=text,
        priority=Priority.HIGH,
        evidence_level=EvidenceLevel.II,
        rationale="Razonamiento.",
        sources=sources,
    )


def _report_con(hypotheses: list[Hypothesis]) -> Report:
    return Report(case_summary="Resumen del caso.", hypotheses=hypotheses)


# ── Comparación de títulos ─────────────────────────────────────────────────────

class TestTitleMatchScore:
    def test_titulos_identicos_dan_uno(self):
        t = "Lead neuropathy: clinical and electrophysiological features"
        assert _title_match_score(t, t) == 1.0

    def test_ignora_mayusculas_acentos_y_puntuacion(self):
        a = "Neuropatía axonal: revisión sistemática"
        b = "NEUROPATIA AXONAL - REVISION SISTEMATICA"
        assert _title_match_score(a, b) == 1.0

    def test_tolera_guion_no_separable_de_los_llm(self):
        a = "Metformin‑associated vitamin B12 deficiency"
        b = "Metformin-associated vitamin B12 deficiency"
        assert _title_match_score(a, b) == 1.0

    def test_tolera_subtitulo_truncado(self):
        citado = "Metformin-associated vitamin B12 deficiency"
        real = "Metformin-associated vitamin B12 deficiency and peripheral neuropathy: a prospective cohort study"
        assert _title_match_score(citado, real) == 1.0

    def test_articulos_distintos_dan_score_bajo(self):
        citado = "Lead neuropathy: clinical and electrophysiological features"
        real = "The role of GABA in the early neuronal development"
        assert _title_match_score(citado, real) < 0.6

    def test_titulo_vacio_no_rompe(self):
        assert _title_match_score("", "cualquier cosa") == 0.0


# ── Veredicto por fuente ───────────────────────────────────────────────────────

class TestVerifyOne:
    def test_pmid_correcto_queda_verificado(self):
        source = _source("12345678", "Lead neuropathy: clinical features")
        meta = {"12345678": {"title": "Lead neuropathy: clinical features"}}
        v = _verify_one(source, meta)
        assert v.status is SourceStatus.VERIFICADA
        assert v.is_valid

    def test_pmid_existente_con_otro_articulo_es_discordante(self):
        """El caso real: el PMID 16512345 existe, pero es de otra cosa."""
        source = _source("16512345", "Lead neuropathy: clinical and electrophysiological features")
        meta = {"16512345": {"title": "The role of GABA in the early neuronal development"}}
        v = _verify_one(source, meta)
        assert v.status is SourceStatus.DISCORDANTE
        assert not v.is_valid
        assert v.actual_title == "The role of GABA in the early neuronal development"

    def test_pmid_ausente_en_pubmed_es_inexistente(self):
        v = _verify_one(_source("99999999", "Estudio inventado"), {})
        assert v.status is SourceStatus.INEXISTENTE
        assert not v.is_valid

    def test_fuente_sin_pmid(self):
        v = _verify_one(_source(None, "Guía clínica sin PMID"), {})
        assert v.status is SourceStatus.SIN_PMID
        assert not v.is_valid


# ── Verificación del reporte completo ──────────────────────────────────────────

class TestVerifyReportSources:
    @pytest.mark.asyncio
    async def test_reporte_sin_fuentes_devuelve_vacio(self):
        report = _report_con([_hypothesis_con([])])
        assert await verify_report_sources(report) == {}

    @pytest.mark.asyncio
    async def test_clasifica_cada_fuente(self, _fake_pubmed):
        _fake_pubmed.metadata = {
            "11111111": {"title": "Neuropatía axonal en diabetes tipo 2"},
            "22222222": {"title": "Corpus callosotomy for drug-resistant epilepsy"},
        }
        report = _report_con([
            _hypothesis_con([
                _source("11111111", "Neuropatía axonal en diabetes tipo 2"),
                _source("22222222", "Deficiencia de vitamina B12 por metformina"),
                _source("33333333", "Estudio que no existe"),
            ])
        ])

        v = await verify_report_sources(report)

        assert v["11111111"].status is SourceStatus.VERIFICADA
        assert v["22222222"].status is SourceStatus.DISCORDANTE
        assert v["33333333"].status is SourceStatus.INEXISTENTE

    @pytest.mark.asyncio
    async def test_deduplica_pmids_repetidos(self, _fake_pubmed):
        _fake_pubmed.metadata = {"11111111": {"title": "Estudio A"}}
        report = _report_con([
            _hypothesis_con([_source("11111111", "Estudio A")], text="H1"),
            _hypothesis_con([_source("11111111", "Estudio A")], text="H2"),
        ])
        assert len(await verify_report_sources(report)) == 1

    @pytest.mark.asyncio
    async def test_fallo_de_red_no_descarta_referencias(self, _fake_pubmed):
        """Un problema de infraestructura no puede invalidar una cita legítima."""
        _fake_pubmed.error = ConnectionError("PubMed caído")
        report = _report_con([_hypothesis_con([_source("11111111", "Estudio A")])])

        v = await verify_report_sources(report)

        assert v["11111111"].status is SourceStatus.NO_VERIFICABLE
        assert not v["11111111"].is_valid


# ── Integración con el reporte exportado ───────────────────────────────────────

class TestReporteEtiquetado:
    @pytest.mark.asyncio
    async def test_hipotesis_con_cita_valida_queda_respaldada(self, _fake_pubmed):
        _fake_pubmed.metadata = {"11111111": {"title": "Estudio A"}}
        hipotesis = _hypothesis_con([_source("11111111", "Estudio A")])
        report = _make_report(hypotheses=[hipotesis])

        v = await verify_report_sources(report)
        export = build_export(_make_case(), report, [], 1.0, verifications=v)

        assert export.hypotheses[0].status == "respaldada"
        assert export.hypotheses[0].verified_sources == 1
        assert export.verification.verificadas == 1
        assert export.verification.hipotesis_respaldadas == 1

    @pytest.mark.asyncio
    async def test_hipotesis_con_pmid_alucinado_queda_especulativa(self, _fake_pubmed):
        _fake_pubmed.metadata = {"16512345": {"title": "The role of GABA in early neuronal development"}}
        hipotesis = _hypothesis_con([_source("16512345", "Lead neuropathy: clinical features")])
        report = _make_report(hypotheses=[hipotesis])

        v = await verify_report_sources(report)
        export = build_export(_make_case(), report, [], 1.0, verifications=v)

        assert export.hypotheses[0].status == "especulativa"
        assert export.verification.discordantes == 1
        assert export.verification.hipotesis_especulativas == 1

    @pytest.mark.asyncio
    async def test_la_especulativa_se_conserva_con_el_titulo_real(self, _fake_pubmed):
        """No se descarta: se muestra etiquetada y con lo que el PMID es en realidad."""
        _fake_pubmed.metadata = {"16512345": {"title": "The role of GABA in early neuronal development"}}
        hipotesis = _hypothesis_con([_source("16512345", "Lead neuropathy: clinical features")])
        report = _make_report(hypotheses=[hipotesis])

        v = await verify_report_sources(report)
        export = build_export(_make_case(), report, [], 1.0, verifications=v)

        assert len(export.hypotheses) == 1
        fuente = export.hypotheses[0].sources[0]
        assert fuente.verified is False
        assert fuente.verification_status == "discordante"
        assert fuente.actual_title == "The role of GABA in early neuronal development"

    def test_sin_verificaciones_todo_queda_especulativo(self):
        """Compatibilidad: build_export sigue funcionando sin el parámetro nuevo."""
        report = _make_report()
        export = build_export(_make_case(), report, [], 1.0)
        assert all(h.status == "especulativa" for h in export.hypotheses)
        assert export.verification.total_fuentes == 0
