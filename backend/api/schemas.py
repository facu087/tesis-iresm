"""
Esquemas de request/response para la API de NEXUS.
"""

from datetime import datetime

from pydantic import BaseModel

from ..models.hypothesis import Source
from ..models.trial import ClinicalTrial, RareDiseaseMatch, TrialSearchSummary

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
    # Nivel EBM efectivo (I | II | III): el declarado por el agente, topeado
    # por la evidencia verificada (backend/pipeline/evidence.py).
    evidence_level: str
    rationale: str
    supporting_agents: list[str]
    sources: list[Source]

    # Estado bibliográfico (Agente 04):
    #   "respaldada"   = al menos una fuente verificada contra PubMed;
    #   "pendiente"    = la verificación no pudo concluir (p. ej. PubMed caído);
    #   "especulativa" = ninguna fuente resiste la verificación.
    # Ninguna se descarta: se muestran etiquetadas para el médico responsable.
    status: str = "especulativa"
    verified_sources: int = 0

    # Trazabilidad del nivel: lo que declaró el agente y por qué quedó así.
    declared_evidence_level: str | None = None  # I | II | III
    evidence_note: str = ""

    # Consenso del Árbitro (Agente 04). Aditivo: un reporte anterior al Árbitro
    # llega con estas listas vacías y se renderiza como antes.
    refuting_agents: list[str] = []
    contradictions: list["ContradictionOut"] = []
    arbiter_note: str = ""           # veredicto del Árbitro, en lenguaje llano
    recitation: str = "no_aplica"    # no_aplica | mejorada | sin_cambio | fallida


class ContradictionOut(BaseModel):
    """Objeción de peso que quedó sin resolver al cerrar el debate."""

    from_agent_name: str
    severity: str            # HIGH | MEDIUM | LOW
    critique_text: str
    alternative: str | None = None


class RecitationOut(BaseModel):
    """Resultado de la Ronda 5: qué pasó cuando se les pidió volver a citar."""

    executed: bool = False
    recited: int = 0         # hipótesis que entraron en la recitación
    improved: int = 0        # las que consiguieron respaldo gracias a ella
    rejected_pmids: int = 0  # fuentes descartadas por PMID fuera del conjunto
    failed_agents: list[str] = []


class ArbitrationOut(BaseModel):
    """
    Resumen del arbitraje (Agente 04).

    `rag_overlap` sobre `cited_sources` es el número que justifica que el
    Árbitro exista: cuántas de las citas de los agentes salieron de la
    literatura que el RAG les había puesto en el prompt.
    """

    status: str = "ok"               # ok | degradado | sin_hipotesis
    input_hypotheses: int = 0        # las que entregó el debate
    consensus_hypotheses: int = 0    # los grupos resultantes
    contradictions: int = 0
    cited_sources: int = 0
    rag_overlap: int = 0
    retrieved_articles: int = 0
    discarded_references: int = 0
    recitation: RecitationOut = RecitationOut()


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

    Respaldadas + pendientes + especulativas = total de hipótesis.
    `hipotesis_topeadas` cuenta las que quedaron con nivel efectivo por debajo
    del declarado por el agente.
    """
    total_fuentes: int = 0
    verificadas: int = 0
    discordantes: int = 0
    inexistentes: int = 0
    sin_pmid: int = 0
    no_verificables: int = 0
    hipotesis_respaldadas: int = 0
    hipotesis_especulativas: int = 0
    hipotesis_pendientes: int = 0
    hipotesis_topeadas: int = 0


class StructuredReport(BaseModel):
    """JSON de exportación completo — alimenta el frontend y la generación de PDF."""
    metadata: ReportMetadata
    case_summary: CaseSummarySection
    hypotheses: list[RankedHypothesis]
    debate_summary: DebateSummary
    clinical_trials: list[ClinicalTrial]
    bibliography: list[Source]
    verification: VerificationSummary = VerificationSummary()

    # Agente 05 — Navegador de Ensayos. Campos aditivos: un reporte anterior
    # al agente valida igual.
    rare_diseases: list[RareDiseaseMatch] = []
    # Nullable a propósito, a diferencia de `verification`: None significa
    # "reporte anterior al Agente 05", y es la señal que usan el frontend y el
    # PDF para renderizar la sección de ensayos como antes. Un default con
    # estados en "sin_consulta" haría que un reporte viejo con ensayos afirme
    # que no se consultó nada.
    trial_search: TrialSearchSummary | None = None

    # Agente 04 — Árbitro Verificador. Nullable por el mismo motivo que
    # `trial_search`: None significa "reporte anterior al Árbitro", y es lo que
    # le dice al frontend y al PDF que las hipótesis vienen sin consolidar.
    arbitration: ArbitrationOut | None = None
