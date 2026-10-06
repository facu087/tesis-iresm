"""
Construcción y enriquecimiento del contexto genómico para el Agente 02.

- build(case): determinista, sin red. Sanea símbolos, detecta estudios negativos
  y construye GenomicContext desde los datos del caso.
- enrich(ctx): consulta PharmGKB (por gen) y ClinVar (por variante) en paralelo.
  Nunca lanza excepción: ante cualquier error actualiza el estado de la fuente
  y devuelve el contexto.
"""

from __future__ import annotations

import asyncio
import re
import sys

from ..external.clinvar import ClinVarClient
from ..external.pharmgkb import PharmGKBClient
from ..external.rate_limiter import ApiUnavailableError, RateLimitError
from ..models.case import ClinicalCase
from ..models.genomics import (
    ClinVarStatus,
    GenomicContext,
    GenomicSource,
    GenomicSourceStatus,
    PharmacogenomicAnnotation,
    VariantClassification,
)

# Siglas que el regex de genes captura pero son enfermedades o abreviaturas clínicas
_NON_GENE_SYMBOLS: frozenset[str] = frozenset({
    "CMT", "FAP", "ATTR", "HMSN", "CIDP", "GBS", "ELA", "ALS",
    "LCR", "EMG", "TAC", "RMN", "MRI", "PCR", "EEG", "ECG", "EKG",
    "VCN", "PET", "SPECT", "RX", "UCI", "UTI", "ACV", "TEC",
    "INN", "OMS", "WHO", "FDA", "EMA", "NCCN", "ESMO",
})

# Palabras clave que marcan un estudio genético como negativo
_NEGATIVE_KEYWORDS: tuple[str, ...] = (
    "negativo", "negativos", "negativa", "negativas",
    "no se detectó", "no se detectaron", "no encontró", "no encontraron",
    "sin mutación", "sin variante", "sin hallazgo",
)

# Número máximo de genes a consultar en PharmGKB por corrida
_MAX_PHARMGKB_GENES = 3

# Número máximo de variantes a consultar en ClinVar por análisis (2 solicitudes c/u)
_MAX_CLINVAR_VARIANTS = 5


def _is_negative_sentence(sentence: str) -> bool:
    """True si la oración contiene una marca de negativo."""
    low = sentence.lower()
    return any(kw in low for kw in _NEGATIVE_KEYWORDS)


def _extract_negative_studies(negative_findings: list[str]) -> list[str]:
    """
    Filtra de negative_findings las entradas que mencionan estudios genéticos.
    """
    genetic_keywords = (
        "gen", "panel", "secuenciación", "secuenciacion", "exoma", "wes",
        "wgs", "variante", "mutación", "mutacion", "cromosóm", "cromosom",
        "array", "fish", "pcr", "ngs",
    )
    result = []
    for entry in negative_findings:
        low = entry.lower()
        if any(kw in low for kw in genetic_keywords):
            result.append(entry)
    return result


def _extract_negative_from_text(raw_text: str) -> list[str]:
    """
    Busca en el texto libre oraciones con estudios genéticos negativos
    (complementa negative_findings cuando el campo llega vacío).
    """
    genetic_kw = re.compile(
        r"\b(?:panel|gen(?:ético|etica|es)?|secuenciación|secuenciacion|"
        r"variante|mutación|mutacion|exoma|wes|wgs|ngs|array|fish)\b",
        re.IGNORECASE,
    )
    results = []
    for sentence in re.split(r"[.;]\s*", raw_text):
        if genetic_kw.search(sentence) and _is_negative_sentence(sentence):
            clean = sentence.strip()
            if clean:
                results.append(clean)
    return results


def build(case: ClinicalCase) -> GenomicContext:
    """
    Construye el GenomicContext de forma determinista, sin red ni LLM.

    Lee case.biomarkers (genes, variants, genetic_findings) y case.pico
    (negative_findings, raw_text) para producir un perfil listo para
    to_prompt_block() y para enrich().
    """
    biomarkers = case.biomarkers

    raw_genes: list[str] = list(biomarkers.genes) if biomarkers else []
    raw_variants: list[str] = list(biomarkers.genetic_variants) if biomarkers else []
    raw_genetic_findings: list[str] = []

    # genetic_findings puede venir del PICO o del perfil de biomarcadores
    if case.pico and case.pico.genetic_findings:
        raw_genetic_findings = list(case.pico.genetic_findings)

    # Separar genes reales de siglas de enfermedad
    genes: list[str] = []
    discarded: list[str] = []
    for sym in raw_genes:
        if sym.strip().upper() in _NON_GENE_SYMBOLS:
            discarded.append(sym)
        else:
            genes.append(sym)

    # Hallazgos genéticos positivos: los de genetic_findings que NO son negativos
    positive_findings: list[str] = [
        f for f in raw_genetic_findings
        if not _is_negative_sentence(f)
    ]

    # Estudios negativos: negative_findings genéticos + oraciones negativas del texto
    negative_studies: list[str] = []
    if case.pico and case.pico.negative_findings:
        negative_studies.extend(_extract_negative_studies(case.pico.negative_findings))
    # También buscar en el texto libre del caso
    negative_studies.extend(_extract_negative_from_text(case.raw_text or ""))
    # Deduplicar manteniendo orden
    seen: set[str] = set()
    unique_negative: list[str] = []
    for entry in negative_studies:
        key = entry.lower().strip()
        if key not in seen:
            seen.add(key)
            unique_negative.append(entry)

    return GenomicContext(
        variants=raw_variants,
        genetic_findings=positive_findings,
        genes=genes,
        discarded_symbols=discarded,
        negative_genetic_studies=unique_negative,
        annotations=[],
        sources=[],
    )


async def _enrich_pharmgkb(ctx: GenomicContext) -> GenomicContext:
    """
    Anotaciones de PharmGKB. Nunca lanza excepción.

    Consulta hasta _MAX_PHARMGKB_GENES genes. Si no hay genes, marca la fuente
    como no_consultada. Cualquier error de red o de la API actualiza el estado
    a no_disponible y devuelve el contexto sin anotaciones.
    """
    if not ctx.genes:
        return ctx.model_copy(update={
            "sources": [GenomicSource(
                name="PharmGKB",
                status=GenomicSourceStatus.no_consultada,
                detail="Sin genes en el caso.",
            )]
        })

    genes_to_query = ctx.genes[:_MAX_PHARMGKB_GENES]
    all_annotations: list[PharmacogenomicAnnotation] = []

    try:
        async with PharmGKBClient() as client:
            for gene in genes_to_query:
                raw_anns = await client.get_gene_annotations(gene)
                for ann in raw_anns:
                    all_annotations.append(PharmacogenomicAnnotation(
                        gene=gene,
                        drug=ann.drug_name,
                        significance=ann.phenotype,
                        level=ann.evidence_level,
                        raw={},
                    ))
    except (ApiUnavailableError, RateLimitError) as exc:
        print(
            f"[NEXUS] PharmGKB no disponible: {type(exc).__name__}",
            file=sys.stderr,
        )
        return ctx.model_copy(update={
            "annotations": all_annotations,
            "sources": [GenomicSource(
                name="PharmGKB",
                status=GenomicSourceStatus.no_disponible,
                detail=str(exc),
            )]
        })
    except Exception as exc:
        print(
            f"[NEXUS] Error inesperado en PharmGKB: {exc}",
            file=sys.stderr,
        )
        return ctx.model_copy(update={
            "annotations": all_annotations,
            "sources": [GenomicSource(
                name="PharmGKB",
                status=GenomicSourceStatus.no_disponible,
                detail=str(exc),
            )]
        })

    status = (
        GenomicSourceStatus.consultada if all_annotations
        else GenomicSourceStatus.sin_resultados
    )
    return ctx.model_copy(update={
        "annotations": all_annotations,
        "sources": [GenomicSource(name="PharmGKB", status=status)],
    })


def pair_variants(ctx: GenomicContext) -> tuple[list[tuple[str, str]], list[str]]:
    """
    Empareja cada variante con su gen, de forma determinista (design.md D4).

    Devuelve (pares gen-variante consultables, variantes sin gen identificable).
    Orden de prioridad: el gen escrito en la propia variante; el gen que comparte
    una frase de `genetic_findings` con la variante; el único gen del caso.
    """
    genes = [g for g in ctx.genes if g]
    pairs: list[tuple[str, str]] = []
    unpaired: list[str] = []
    for raw in ctx.variants:
        variant = raw.strip()
        gene = next((g for g in genes if re.search(rf"\b{re.escape(g)}\b", variant)), None)
        if gene:
            variant = re.sub(rf"\b{re.escape(gene)}\b[:\s]*", "", variant).strip()
        else:
            for finding in ctx.genetic_findings:
                if variant in finding:
                    gene = next(
                        (g for g in genes if re.search(rf"\b{re.escape(g)}\b", finding)), None
                    )
                    if gene:
                        break
        if gene is None and len(genes) == 1:
            gene = genes[0]
        if gene and variant and (gene, variant) not in pairs:
            pairs.append((gene, variant))
        elif not gene:
            unpaired.append(raw)
    return pairs, unpaired


def _clinvar_source(results: list[VariantClassification], detail: str) -> GenomicSource:
    statuses = {r.status for r in results}
    if ClinVarStatus.encontrada in statuses:
        status = GenomicSourceStatus.consultada
    elif statuses == {ClinVarStatus.no_disponible}:
        status = GenomicSourceStatus.no_disponible
    else:
        status = GenomicSourceStatus.sin_resultados
    return GenomicSource(name="ClinVar", status=status, detail=detail)


async def _enrich_clinvar(ctx: GenomicContext) -> tuple[list[VariantClassification], GenomicSource]:
    """Clasificaciones de ClinVar para las variantes del caso. Nunca lanza excepción."""
    pairs, unpaired = pair_variants(ctx)
    notes: list[str] = []
    if unpaired:
        notes.append(f"{len(unpaired)} variante(s) sin gen identificable, no consultadas")
    if len(pairs) > _MAX_CLINVAR_VARIANTS:
        notes.append(f"{len(pairs) - _MAX_CLINVAR_VARIANTS} variante(s) sobre el máximo de "
                     f"{_MAX_CLINVAR_VARIANTS}, no consultadas")
        pairs = pairs[:_MAX_CLINVAR_VARIANTS]
    detail = "; ".join(notes)

    if not pairs:
        return [], GenomicSource(
            name="ClinVar", status=GenomicSourceStatus.no_consultada,
            detail=detail or "Sin variantes en el caso.",
        )

    try:
        async with ClinVarClient() as client:
            results = [await client.classify(gene, variant) for gene, variant in pairs]
    except Exception as exc:
        print(f"[NEXUS] ClinVar no disponible: {type(exc).__name__}", file=sys.stderr)
        results = [
            VariantClassification(gene=g, variant=v, status=ClinVarStatus.no_disponible,
                                  detail=type(exc).__name__)
            for g, v in pairs
        ]
    return results, _clinvar_source(results, detail)


async def enrich(ctx: GenomicContext) -> GenomicContext:
    """
    Enriquece el contexto con PharmGKB (por gen) y ClinVar (por variante), en
    paralelo. Nunca lanza excepción; las dos fuentes quedan en `sources`.
    """
    pharm_ctx, (clinvar, clinvar_source) = await asyncio.gather(
        _enrich_pharmgkb(ctx), _enrich_clinvar(ctx)
    )
    return pharm_ctx.model_copy(update={
        "clinvar": clinvar,
        "sources": [*pharm_ctx.sources, clinvar_source],
    })
