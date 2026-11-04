"""
Modelos de datos para el caso clínico y la síntesis PICO.

PICO = Población / Intervención / Comparación / Outcome
Metodología estándar de medicina basada en evidencia para formular
preguntas clínicas claras y reproducibles.
"""

from __future__ import annotations

from pydantic import BaseModel
from .biomarkers import BiomarkerProfile
from .genomics import GenomicContext


class PICOSynthesis(BaseModel):
    # P — Población
    patient_profile: str          # Descripción demográfica y clínica del paciente
    chief_complaint: str          # Motivo de consulta principal
    condition_en: str = ""        # Condición en inglés médico, para APIs externas (todas son en inglés)
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
    # Texto clínico ya normalizado y anonimizado. El comentario anterior decía
    # "ya anonimizado" cuando no existía ninguna anonimización: era un supuesto
    # sobre quien cargaba el archivo, no un control. Desde el Sprint 5 el router
    # pasa el texto por ingestion/anonimizador.py antes de construir el caso.
    raw_text: str
    pico: PICOSynthesis | None = None           # Se completa tras el análisis PICO
    biomarkers: BiomarkerProfile | None = None  # Se completa tras la extracción de biomarcadores
    genomic_context: GenomicContext | None = None  # Se completa en la Ronda 1 (Agente 02)
