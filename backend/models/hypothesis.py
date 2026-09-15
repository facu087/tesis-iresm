from enum import Enum
from pydantic import BaseModel


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceLevel(str, Enum):
    I = "I"      # Revisiones sistemáticas / meta-análisis / RCTs
    II = "II"    # Estudios de cohorte / caso-control
    III = "III"  # Series de casos / opinión de expertos / especulativo


class Source(BaseModel):
    pmid: str | None = None
    title: str
    journal: str | None = None
    year: int | None = None
    url: str | None = None

    # Resultado de la verificación contra PubMed (Agente 04). Se completa en
    # backend/pipeline/verification.py; None = todavía no se verificó.
    verified: bool | None = None
    verification_status: str | None = None  # ver SourceStatus
    actual_title: str | None = None  # título real en PubMed, si no coincide
    # Tipos de publicación que indexa PubMed ("Meta-Analysis", "Case Reports"…).
    # Solo se completan para fuentes verificadas (backend/pipeline/evidence.py).
    publication_types: list[str] = []


class Hypothesis(BaseModel):
    text: str
    priority: Priority
    evidence_level: EvidenceLevel
    rationale: str
    sources: list[Source] = []
