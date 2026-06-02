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


class Hypothesis(BaseModel):
    text: str
    priority: Priority
    evidence_level: EvidenceLevel
    rationale: str
    sources: list[Source] = []
