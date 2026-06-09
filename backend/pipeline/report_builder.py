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
)
from ..models.case import ClinicalCase
from ..models.hypothesis import EvidenceLevel, Priority, Source
from ..models.report import AgentOutput, Report
from ..models.trial import ClinicalTrial

_VERSION = "0.3.0"

# Pesos para ordenar hipótesis por relevancia
_PRIORITY_WEIGHT = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
_EVIDENCE_WEIGHT = {EvidenceLevel.I: 0, EvidenceLevel.II: 1, EvidenceLevel.III: 2}


def _rank_hypotheses(report: Report) -> list[RankedHypothesis]:
    """
    Ordena las hipótesis finales por prioridad y nivel de evidencia,
    y determina qué agentes las respaldaron en sus outputs de Ronda 1.
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

    sorted_hypotheses = sorted(
        report.hypotheses,
        key=lambda h: (
            _PRIORITY_WEIGHT.get(h.priority, 9),
            _EVIDENCE_WEIGHT.get(h.evidence_level, 9),
        ),
    )

    return [
        RankedHypothesis(
            rank=i + 1,
            text=h.text,
            priority=h.priority.value,
            evidence_level=h.evidence_level.value,
            rationale=h.rationale,
            supporting_agents=agent_support.get(h.text, []),
            sources=h.sources,
        )
        for i, h in enumerate(sorted_hypotheses)
    ]


def _build_bibliography(report: Report) -> list[Source]:
    """Consolida todas las fuentes únicas del reporte, ordenadas por PMID."""
    seen: set[str] = set()
    bibliography: list[Source] = []
    for h in report.hypotheses:
        for source in h.sources:
            key = source.pmid or source.title
            if key and key not in seen:
                seen.add(key)
                bibliography.append(source)
    return sorted(bibliography, key=lambda s: s.pmid or "")


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
) -> StructuredReport:
    """
    Ensambla el StructuredReport de exportación a partir de los outputs del pipeline.

    Args:
        case:             ClinicalCase con PICO y biomarcadores ya construidos.
        report:           Report final del motor de debate (Rondas 1–4).
        trials:           Ensayos clínicos encontrados en ClinicalTrials.gov.
        processing_time:  Tiempo total de procesamiento en segundos.

    Returns:
        StructuredReport listo para serializar a JSON o exportar a PDF.
    """
    return StructuredReport(
        metadata=ReportMetadata(
            generated_at=datetime.now(timezone.utc),
            nexus_version=_VERSION,
            processing_time_seconds=round(processing_time, 2),
        ),
        case_summary=_build_case_summary(case, report),
        hypotheses=_rank_hypotheses(report),
        debate_summary=_build_debate_summary(report),
        clinical_trials=trials,
        bibliography=_build_bibliography(report),
    )
