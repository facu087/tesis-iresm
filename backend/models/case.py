"""
Modelos de datos para el caso clínico y la síntesis PICO.

PICO = Población / Intervención / Comparación / Outcome
Metodología estándar de medicina basada en evidencia para formular
preguntas clínicas claras y reproducibles.
"""

from pydantic import BaseModel


class PICOSynthesis(BaseModel):
    # P — Población
    patient_profile: str          # Descripción demográfica y clínica del paciente
    chief_complaint: str          # Motivo de consulta principal
    relevant_history: list[str]   # Antecedentes relevantes (familiares, personales)
    negative_findings: list[str]  # Estudios negativos relevantes (importante para diagnóstico diferencial)
    disease_duration: str         # Tiempo de evolución

    # I — Intervención / Exposición
    current_treatments: list[str]  # Tratamientos actuales o previos
    procedures_done: list[str]     # Procedimientos realizados (EMG, LCR, biopsias, etc.)

    # C — Comparación
    comparison: str               # Contexto de comparación o "No aplica"

    # O — Outcome
    primary_outcome: str          # Objetivo principal de la investigación
    secondary_outcomes: list[str] # Objetivos secundarios

    # Extras extraídos del texto
    biomarkers: list[str]         # Biomarcadores mencionados
    genetic_findings: list[str]   # Hallazgos genéticos relevantes

    # Narrativa estructurada final (lo que se pasa a los agentes)
    clinical_narrative: str


class ClinicalCase(BaseModel):
    raw_text: str                        # Texto clínico original (ya anonimizado)
    pico: PICOSynthesis | None = None    # Se completa después del análisis PICO
