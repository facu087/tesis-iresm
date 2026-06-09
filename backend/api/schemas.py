"""
Esquemas de request/response para la API de NEXUS.
"""

from pydantic import BaseModel

from ..models.report import Report
from ..models.trial import ClinicalTrial


class AnalyzeResponse(BaseModel):
    """Respuesta del endpoint POST /api/analyze."""
    report: Report
    trials: list[ClinicalTrial]
    processing_time_seconds: float
