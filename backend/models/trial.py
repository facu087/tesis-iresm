"""
Modelo de datos para ensayos clínicos obtenidos de ClinicalTrials.gov.
"""

from pydantic import BaseModel


class ClinicalTrial(BaseModel):
    nct_id: str                          # Identificador NCT (ej: "NCT04123456")
    title: str                           # Título breve del ensayo
    status: str                          # Estado (RECRUITING, ACTIVE_NOT_RECRUITING, etc.)
    brief_summary: str                   # Resumen del ensayo
    conditions: list[str] = []           # Condiciones/enfermedades estudiadas
    phase: str | None = None             # Fase (PHASE1, PHASE2, PHASE3, PHASE4, NA)
    sponsor: str | None = None           # Patrocinador principal
    start_date: str | None = None        # Fecha de inicio (YYYY-MM)
    completion_date: str | None = None   # Fecha estimada de finalización
    eligibility_criteria: str | None = None  # Criterios de inclusión/exclusión
    min_age: str | None = None           # Edad mínima requerida
    max_age: str | None = None           # Edad máxima requerida
    sex: str | None = None               # Sexo (ALL, MALE, FEMALE)
    locations: list[str] = []            # Países donde se realiza
    url: str = ""                        # URL en ClinicalTrials.gov

    def summary_line(self) -> str:
        """Línea compacta para mostrar en reportes."""
        phase_str = f" | {self.phase}" if self.phase and self.phase != "NA" else ""
        return f"{self.nct_id}{phase_str} — {self.title[:80]}"
