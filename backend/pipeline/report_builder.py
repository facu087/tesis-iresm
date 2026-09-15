"""
Builder del reporte estructurado de exportación.

Transforma los outputs internos del pipeline en un StructuredReport listo
para consumir desde el frontend y para la generación de PDF.

En Sprint 4, el Agente 06 (Sintetizador) reemplazará este módulo con
síntesis LLM-asistida. El contrato del JSON (StructuredReport) no cambia.
"""

from datetime import datetime, timezone

from ..api.schemas import (
    CaseSummarySection,
    DebateSummary,
    RankedHypothesis,
    ReportMetadata,
    StructuredReport,
    VerificationSummary,
)
from ..models.case import ClinicalCase
from ..models.hypothesis import Source
from ..models.report import Report
from ..models.trial import ClinicalTrial
from .evidence import HypothesisStatus, prioritize
from .verification import SourceStatus, SourceVerification, source_key

_VERSION = "0.3.0"


def _annotate_source(
    source: Source, verifications: dict[str, SourceVerification]
) -> Source:
    """
    Devuelve una copia de la fuente con el veredicto de la verificación.

    Los campos de verificación salen solo del veredicto: si la fuente no tiene
    veredicto se limpian, porque un LLM puede haberlos escrito en su JSON
    (p. ej. `verified: true`). Los tipos de publicación se exportan solo para
    fuentes verificadas. No modifica la original: el Report interno queda intacto.
    """
    clave = source_key(source)
    veredicto = verifications.get(clave) if clave else None
    if veredicto is None:
        return source.model_copy(
            update={
                "verified": None,
                "verification_status": None,
                "actual_title": None,
                "publication_types": [],
            }
        )
    return source.model_copy(
        update={
            "verified": veredicto.is_valid,
            "verification_status": veredicto.status.value,
            "actual_title": veredicto.actual_title or None,
            "publication_types": (
                list(veredicto.publication_types) if veredicto.is_valid else []
            ),
        }
    )


def _rank_hypotheses(
    report: Report, verifications: dict[str, SourceVerification]
) -> list[RankedHypothesis]:
    """
    Clasifica y ordena las hipótesis finales con las reglas EBM de
    `evidence.prioritize()` (estado → nivel efectivo → prioridad → fuentes
    verificadas) y determina qué agentes las respaldaron en Ronda 1 y en la
    última ronda del debate.
    """
    # Índice: texto de hipótesis → agentes que la propusieron (Ronda 1)
    agent_support: dict[str, list[str]] = {}
    for output in report.agent_outputs:
        for h in output.hypotheses:
            agent_support.setdefault(h.text, []).append(output.agent_name)

    # Si hay rondas de debate, sumar agentes de Ronda 4 (revisiones finales)
    if report.debate_rounds:
        last_round = report.debate_rounds[-1]
        for output in last_round.agent_outputs:
            for h in output.hypotheses:
                existing = agent_support.get(h.text, [])
                if output.agent_name not in existing:
                    agent_support.setdefault(h.text, []).append(output.agent_name)

    ranked: list[RankedHypothesis] = []
    for i, (h, evaluacion) in enumerate(prioritize(report.hypotheses, verifications)):
        ranked.append(
            RankedHypothesis(
                rank=i + 1,
                text=h.text,
                priority=h.priority.value,
                # Nivel efectivo: el declarado, topeado por la evidencia verificada.
                evidence_level=evaluacion.effective_level.value,
                rationale=h.rationale,
                supporting_agents=agent_support.get(h.text, []),
                sources=[_annotate_source(s, verifications) for s in h.sources],
                # Sin ninguna referencia que resista la verificación la hipótesis
                # queda especulativa (o pendiente si PubMed no respondió), pero
                # se conserva y se muestra.
                status=evaluacion.status.value,
                verified_sources=evaluacion.verified_sources,
                declared_evidence_level=evaluacion.declared_level.value,
                evidence_note=evaluacion.note,
            )
        )
    return ranked


def _build_bibliography(
    report: Report, verifications: dict[str, SourceVerification]
) -> list[Source]:
    """Consolida todas las fuentes únicas del reporte, ordenadas por PMID."""
    seen: set[str] = set()
    bibliography: list[Source] = []
    for h in report.hypotheses:
        for source in h.sources:
            key = source.pmid or source.title
            if key and key not in seen:
                seen.add(key)
                bibliography.append(_annotate_source(source, verifications))
    return sorted(bibliography, key=lambda s: s.pmid or "")


def _build_verification_summary(
    verifications: dict[str, SourceVerification],
    hypotheses: list[RankedHypothesis],
) -> VerificationSummary:
    """Cuenta el resultado de la verificación bibliográfica para el reporte."""
    conteo = {status: 0 for status in SourceStatus}
    for veredicto in verifications.values():
        conteo[veredicto.status] += 1

    por_estado = {status: 0 for status in HypothesisStatus}
    for h in hypotheses:
        por_estado[HypothesisStatus(h.status)] += 1

    topeadas = sum(
        1 for h in hypotheses
        if h.declared_evidence_level and h.evidence_level != h.declared_evidence_level
    )
    return VerificationSummary(
        total_fuentes=len(verifications),
        verificadas=conteo[SourceStatus.VERIFICADA],
        discordantes=conteo[SourceStatus.DISCORDANTE],
        inexistentes=conteo[SourceStatus.INEXISTENTE],
        sin_pmid=conteo[SourceStatus.SIN_PMID],
        no_verificables=conteo[SourceStatus.NO_VERIFICABLE],
        hipotesis_respaldadas=por_estado[HypothesisStatus.RESPALDADA],
        hipotesis_pendientes=por_estado[HypothesisStatus.PENDIENTE],
        hipotesis_especulativas=por_estado[HypothesisStatus.ESPECULATIVA],
        hipotesis_topeadas=topeadas,
    )


def _build_debate_summary(report: Report) -> DebateSummary:
    total_critiques = sum(
        len(r.critiques) for r in report.debate_rounds
    )
    has_high_divergences = any(
        "HIGH" in d for d in report.divergences
    )
    return DebateSummary(
        rounds_completed=len(report.debate_rounds) + 1,  # +1 por Ronda 1
        total_critiques=total_critiques,
        divergences=report.divergences,
        consensus_reached=not has_high_divergences,
    )


def _build_case_summary(case: ClinicalCase, report: Report) -> CaseSummarySection:
    if case.pico:
        return CaseSummarySection(
            narrative=case.pico.clinical_narrative,
            patient_profile=case.pico.patient_profile,
            chief_complaint=case.pico.chief_complaint,
            disease_duration=case.pico.disease_duration,
            current_treatments=case.pico.current_treatments,
            relevant_history=case.pico.relevant_history,
            procedures_done=case.pico.procedures_done,
        )
    return CaseSummarySection(narrative=report.case_summary)


def build_export(
    case: ClinicalCase,
    report: Report,
    trials: list[ClinicalTrial],
    processing_time: float,
    verifications: dict[str, SourceVerification] | None = None,
) -> StructuredReport:
    """
    Ensambla el StructuredReport de exportación a partir de los outputs del pipeline.

    Args:
        case:             ClinicalCase con PICO y biomarcadores ya construidos.
        report:           Report final del motor de debate (Rondas 1–4).
        trials:           Ensayos clínicos encontrados en ClinicalTrials.gov.
        processing_time:  Tiempo total de procesamiento en segundos.
        verifications:    Veredictos de verify_report_sources(). Si se omite,
                          ninguna fuente queda verificada y todas las hipótesis
                          se etiquetan como especulativas.

    Returns:
        StructuredReport listo para serializar a JSON o exportar a PDF.
    """
    verifications = verifications or {}
    hypotheses = _rank_hypotheses(report, verifications)

    return StructuredReport(
        metadata=ReportMetadata(
            generated_at=datetime.now(timezone.utc),
            nexus_version=_VERSION,
            processing_time_seconds=round(processing_time, 2),
        ),
        case_summary=_build_case_summary(case, report),
        hypotheses=hypotheses,
        debate_summary=_build_debate_summary(report),
        clinical_trials=trials,
        bibliography=_build_bibliography(report, verifications),
        verification=_build_verification_summary(verifications, hypotheses),
    )
