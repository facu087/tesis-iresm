"""
Esquemas de request/response para la API de NEXUS.
"""

from datetime import datetime

from pydantic import BaseModel

from ..models.hypothesis import Source
from ..models.trial import ClinicalTrial

_DISCLAIMER = (
    "NEXUS es un sistema de soporte investigativo. "
    "No emite diagnósticos clínicos. "
    "Las hipótesis generadas son orientativas y deben ser evaluadas "
    "por el médico responsable antes de tomar decisiones clínicas."
)


class ReportMetadata(BaseModel):
    generated_at: datetime
    nexus_version: str
    processing_time_seconds: float
    disclaimer: str = _DISCLAIMER


class CaseSummarySection(BaseModel):
    narrative: str
    patient_profile: str = ""
    chief_complaint: str = ""
    disease_duration: str = ""
    current_treatments: list[str] = []
    relevant_history: list[str] = []
    procedures_done: list[str] = []


class RankedHypothesis(BaseModel):
    rank: int
    text: str
    priority: str            # HIGH | MEDIUM | LOW
    evidence_level: str      # I | II | III
    rationale: str
    supporting_agents: list[str]
    sources: list[Source]

    # Estado bibliográfico (Agente 04). "respaldada" = al menos una fuente
    # verificada contra PubMed; "especulativa" = ninguna. Las especulativas
    # NO se descartan: se muestran etiquetadas para el médico responsable.
    status: str = "especulativa"
    verified_sources: int = 0


class DebateSummary(BaseModel):
    rounds_completed: int
    total_critiques: int
    divergences: list[str]
    consensus_reached: bool


class VerificationSummary(BaseModel):
    """
    Resultado de contrastar contra PubMed las referencias citadas por los agentes.

    `discordantes` son PMIDs que existen pero corresponden a otro artículo:
    el caso típico de alucinación de un LLM.
    """
    total_fuentes: int = 0
    verificadas: int = 0
    discordantes: int = 0
    inexistentes: int = 0
    sin_pmid: int = 0
    no_verificables: int = 0
    hipotesis_respaldadas: int = 0
    hipotesis_especulativas: int = 0


class StructuredReport(BaseModel):
    """JSON de exportación completo — alimenta el frontend y la generación de PDF."""
    metadata: ReportMetadata
    case_summary: CaseSummarySection
    hypotheses: list[RankedHypothesis]
    debate_summary: DebateSummary
    clinical_trials: list[ClinicalTrial]
    bibliography: list[Source]
    verification: VerificationSummary = VerificationSummary()
