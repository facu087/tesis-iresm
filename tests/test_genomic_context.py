"""
Tests de backend/pipeline/genomic_context.py y backend/models/genomics.py.

Tests unitarios: sin red, sin LLM. PharmGKB se mockea en las secciones async.
Caso base: neuropatía axonal sensitivomotora, hombre de 42 años.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.external.pharmgkb import GeneAnnotation
from backend.external.rate_limiter import ApiUnavailableError, RateLimitError
from backend.models.biomarkers import BiomarkerProfile
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.genomics import (
    GenomicContext,
    GenomicSource,
    GenomicSourceStatus,
    PharmacogenomicAnnotation,
)
from backend.pipeline import genomic_context as gc_module
from backend.pipeline.genomic_context import build, enrich

# ── Fixtures ──────────────────────────────────────────────────────────────────

CASO_BASE_TEXTO = (
    "Paciente masculino de 42 años con neuropatía axonal sensitivomotora progresiva "
    "de 18 meses de evolución. Panel genético reducido (CMT panel de 40 genes) negativo. "
    "Anticuerpos paraneoplásicos (anti-Hu, anti-Yo, anti-Ri) negativos."
)


def _pico_caso_base() -> PICOSynthesis:
    return PICOSynthesis(
        patient_profile="Masculino, 42 años",
        chief_complaint="Neuropatía axonal sensitivomotora",
        condition_en="axonal sensorimotor polyneuropathy",
        relevant_history=["Padre con trastorno de la marcha no estudiado"],
        negative_findings=["Panel CMT de 40 genes negativo"],
        disease_duration="18 meses",
        current_treatments=[],
        procedures_done=["Electromiograma", "Punción lumbar"],
        comparison="No aplica",
        primary_outcome="Identificar etiología",
        secondary_outcomes=[],
        biomarkers=[],
        genetic_findings=[],
        clinical_narrative="Varón de 42 años con neuropatía axonal de 18 meses.",
    )


def _biomarkers_con_cmt() -> BiomarkerProfile:
    """Estado real que devuelve hoy la capa regex: genes=['CMT']."""
    return BiomarkerProfile(
        genes=["CMT"],
        antibodies=["anti-Hu", "anti-Yo", "anti-Ri"],
        lab_biomarkers=[],
        genetic_variants=[],
        pathways=[],
        drugs=[],
        procedures=["Electromiograma", "Punción lumbar"],
        surgeries=[],
    )


def _caso_base() -> ClinicalCase:
    return ClinicalCase(
        raw_text=CASO_BASE_TEXTO,
        pico=_pico_caso_base(),
        biomarkers=_biomarkers_con_cmt(),
    )


# ── Sección 1: build() — determinista, sin red ────────────────────────────────


class TestBuildCasoBase:
    """El caso base no tiene variantes ni hallazgos positivos."""

    def test_cmt_descartado(self):
        ctx = build(_caso_base())
        assert "CMT" not in ctx.genes

    def test_cmt_en_discarded(self):
        ctx = build(_caso_base())
        assert "CMT" in ctx.discarded_symbols

    def test_sin_variantes(self):
        ctx = build(_caso_base())
        assert ctx.variants == []

    def test_sin_hallazgos_positivos(self):
        ctx = build(_caso_base())
        assert ctx.genetic_findings == []

    def test_modo_sin_hallazgos(self):
        ctx = build(_caso_base())
        assert not ctx.has_genomic_findings

    def test_estudio_negativo_detectado_desde_negative_findings(self):
        ctx = build(_caso_base())
        assert any("panel" in e.lower() or "gen" in e.lower() for e in ctx.negative_genetic_studies)

    def test_estudio_negativo_detectado_desde_texto_libre(self):
        """El texto libre también puede tener estudios negativos."""
        caso = ClinicalCase(
            raw_text="Panel genético CMT de 40 genes negativo. Resto normal.",
            pico=_pico_caso_base(),
            biomarkers=_biomarkers_con_cmt(),
        )
        ctx = build(caso)
        assert ctx.negative_genetic_studies


class TestBuildConVariantes:
    """Caso con TTR y p.Val30Met."""

    def _caso_ttr(self) -> ClinicalCase:
        pico = _pico_caso_base()
        pico.genetic_findings = ["Variante p.Val30Met en gen TTR heterocigoto"]
        return ClinicalCase(
            raw_text="Variante p.Val30Met en el gen TTR identificada.",
            pico=pico,
            biomarkers=BiomarkerProfile(
                genes=["TTR"],
                antibodies=[],
                lab_biomarkers=[],
                genetic_variants=["p.Val30Met"],
                pathways=[],
                drugs=[],
                procedures=[],
                surgeries=[],
            ),
        )

    def test_variante_presente(self):
        ctx = build(self._caso_ttr())
        assert "p.Val30Met" in ctx.variants

    def test_gen_ttr_en_genes(self):
        ctx = build(self._caso_ttr())
        assert "TTR" in ctx.genes

    def test_modo_con_hallazgos(self):
        ctx = build(self._caso_ttr())
        assert ctx.has_genomic_findings

    def test_hallazgo_positivo_no_es_negativo(self):
        ctx = build(self._caso_ttr())
        assert ctx.genetic_findings


class TestBuildEdgeCases:
    def test_pmp22_solo_mencionado_sin_variante(self):
        """Gen mencionado pero sin variante = va a genes, not genetic_findings."""
        caso = ClinicalCase(
            raw_text="Se evaluó PMP22 sin resultado.",
            pico=_pico_caso_base(),
            biomarkers=BiomarkerProfile(
                genes=["PMP22"], antibodies=[], lab_biomarkers=[],
                genetic_variants=[], pathways=[], drugs=[], procedures=[], surgeries=[],
            ),
        )
        ctx = build(caso)
        assert "PMP22" in ctx.genes
        assert ctx.genetic_findings == []

    def test_entrada_sin_biomarkers(self):
        caso = ClinicalCase(raw_text="Texto.", pico=_pico_caso_base(), biomarkers=None)
        ctx = build(caso)
        assert isinstance(ctx, GenomicContext)
        assert ctx.genes == []

    def test_genetic_finding_negativo_no_va_a_positivos(self):
        """Una entrada de genetic_findings que dice 'negativo' no es un hallazgo positivo."""
        pico = _pico_caso_base()
        pico.genetic_findings = ["Estudio de gen PMP22 negativo"]
        caso = ClinicalCase(
            raw_text=CASO_BASE_TEXTO,
            pico=pico,
            biomarkers=_biomarkers_con_cmt(),
        )
        ctx = build(caso)
        assert ctx.genetic_findings == []

    def test_reproducible(self):
        """build() con la misma entrada siempre produce el mismo resultado."""
        ctx1 = build(_caso_base())
        ctx2 = build(_caso_base())
        assert ctx1.model_dump() == ctx2.model_dump()


class TestPromptBlock:
    def test_modo_sin_hallazgos_dice_no_hay_variantes(self):
        ctx = build(_caso_base())
        bloque = ctx.to_prompt_block()
        assert "No se reportan variantes" in bloque

    def test_modo_sin_hallazgos_con_genes_mencionados(self):
        """Genes mencionados sin variante aparecen en el bloque."""
        caso = ClinicalCase(
            raw_text="PMP22 fue evaluado.",
            pico=_pico_caso_base(),
            biomarkers=BiomarkerProfile(
                genes=["PMP22"], antibodies=[], lab_biomarkers=[],
                genetic_variants=[], pathways=[], drugs=[], procedures=[], surgeries=[],
            ),
        )
        ctx = build(caso)
        bloque = ctx.to_prompt_block()
        assert "PMP22" in bloque

    def test_fuente_no_consultada_aparece_en_bloque(self):
        ctx = GenomicContext(
            sources=[GenomicSource(name="PharmGKB", status=GenomicSourceStatus.no_consultada)]
        )
        assert "no consultada" in ctx.to_prompt_block()

    def test_fuente_no_disponible_aparece_en_bloque(self):
        ctx = GenomicContext(
            sources=[GenomicSource(name="PharmGKB", status=GenomicSourceStatus.no_disponible)]
        )
        assert "no disponible" in ctx.to_prompt_block()

    def test_fuente_sin_resultados_aparece_en_bloque(self):
        ctx = GenomicContext(
            sources=[GenomicSource(name="PharmGKB", status=GenomicSourceStatus.sin_resultados)]
        )
        assert "sin anotaciones" in ctx.to_prompt_block()


# ── Sección 2: enrich() — PharmGKB ───────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_pharmgkb_breaker():
    """Fixture vacío — el breaker vive dentro de PharmGKBClient, que se mockea."""
    yield


def _make_mock_client(anns_by_gene: dict[str, list[GeneAnnotation]] | None = None):
    """Crea un mock de PharmGKBClient que devuelve anotaciones por gen."""
    anns_by_gene = anns_by_gene or {}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    async def get_gene_annotations(gene: str, max_results: int = 10):
        return anns_by_gene.get(gene, [])

    mock_client.get_gene_annotations = get_gene_annotations
    return mock_client


def _gene_ann(gene: str, drug: str, level: str = "1A") -> GeneAnnotation:
    return GeneAnnotation(
        gene_symbol=gene,
        drug_name=drug,
        phenotype="efficacy",
        evidence_level=level,
        variant="",
        population="",
        url="",
    )


class TestEnrichSinGenes:
    def test_sin_genes_no_consulta_pharmgkb(self):
        ctx = GenomicContext()
        with patch("backend.pipeline.genomic_context.PharmGKBClient") as mock_cls:
            resultado = asyncio.run(enrich(ctx))
        mock_cls.assert_not_called()
        assert resultado.sources[0].status == GenomicSourceStatus.no_consultada

    def test_sin_genes_devuelve_contexto(self):
        ctx = GenomicContext()
        resultado = asyncio.run(enrich(ctx))
        assert isinstance(resultado, GenomicContext)


class TestEnrichConGenes:
    def _ctx_con_genes(self, genes: list[str]) -> GenomicContext:
        return GenomicContext(genes=genes)

    def test_cinco_genes_solo_hace_tres_consultas(self):
        ctx = self._ctx_con_genes(["TTR", "PMP22", "MPZ", "GJB1", "MFN2"])
        llamadas: list[str] = []

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def get_gene_annotations(gene: str, max_results: int = 10):
            llamadas.append(gene)
            return []

        mock_client.get_gene_annotations = get_gene_annotations

        with patch("backend.pipeline.genomic_context.PharmGKBClient", return_value=mock_client):
            asyncio.run(enrich(ctx))

        assert len(llamadas) == 3

    def test_con_anotaciones_estado_consultada(self):
        ctx = self._ctx_con_genes(["TTR"])
        ann = _gene_ann("TTR", "tafamidis")
        mock_client = _make_mock_client({"TTR": [ann]})
        with patch("backend.pipeline.genomic_context.PharmGKBClient", return_value=mock_client):
            resultado = asyncio.run(enrich(ctx))
        assert resultado.sources[0].status == GenomicSourceStatus.consultada
        assert len(resultado.annotations) == 1
        assert resultado.annotations[0].drug == "tafamidis"

    def test_respuesta_vacia_estado_sin_resultados(self):
        ctx = self._ctx_con_genes(["TTR"])
        mock_client = _make_mock_client()
        with patch("backend.pipeline.genomic_context.PharmGKBClient", return_value=mock_client):
            resultado = asyncio.run(enrich(ctx))
        assert resultado.sources[0].status == GenomicSourceStatus.sin_resultados

    def test_503_estado_no_disponible_no_lanza(self):
        ctx = self._ctx_con_genes(["TTR"])
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(
            side_effect=ApiUnavailableError("PharmGKB", "503", 503)
        )
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("backend.pipeline.genomic_context.PharmGKBClient", return_value=mock_client):
            resultado = asyncio.run(enrich(ctx))
        assert resultado.sources[0].status == GenomicSourceStatus.no_disponible

    def test_rate_limit_estado_no_disponible_no_lanza(self):
        ctx = self._ctx_con_genes(["TTR"])
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(
            side_effect=RateLimitError("PharmGKB", "429", 429)
        )
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("backend.pipeline.genomic_context.PharmGKBClient", return_value=mock_client):
            resultado = asyncio.run(enrich(ctx))
        assert resultado.sources[0].status == GenomicSourceStatus.no_disponible

    def test_anonimizacion_solo_simbolos_en_la_consulta(self):
        """La consulta a PharmGKB solo envía el símbolo del gen, nunca narrativa clínica."""
        ctx = self._ctx_con_genes(["TTR"])
        llamadas: list[str] = []

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def get_gene_annotations(gene: str, max_results: int = 10):
            llamadas.append(gene)
            return []

        mock_client.get_gene_annotations = get_gene_annotations

        with patch("backend.pipeline.genomic_context.PharmGKBClient", return_value=mock_client):
            asyncio.run(enrich(ctx))

        assert llamadas == ["TTR"]
        for llamada in llamadas:
            assert "neuropatía" not in llamada.lower()
            assert "42" not in llamada
