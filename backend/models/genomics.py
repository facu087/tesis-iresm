"""
Modelos de datos para el contexto genómico del Agente 02 (Especialista Genómica).

GenomicContext encapsula todo lo que el agente necesita del caso: genes saneados,
variantes, hallazgos negativos y anotaciones farmacogenómicas de PharmGKB.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GenomicSourceStatus(str, Enum):
    """Estado de la consulta a una fuente genómica externa."""

    consultada = "consultada"
    sin_resultados = "sin_resultados"
    no_disponible = "no_disponible"
    no_consultada = "no_consultada"


class GenomicSource(BaseModel):
    """Resultado de consultar una fuente genómica (PharmGKB, ClinVar, etc.)."""

    name: str
    status: GenomicSourceStatus
    detail: str = ""


class PharmacogenomicAnnotation(BaseModel):
    """Anotación farmacogenómica de PharmGKB para un gen."""

    gene: str
    drug: str
    significance: str = ""
    level: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class GenomicContext(BaseModel):
    """
    Perfil genómico del caso clínico, armado de forma determinista antes de
    invocar al Agente 02.

    Campos:
    - variants: variantes genéticas explícitas del caso (p.Val30Met, c.148G>A).
    - genetic_findings: hallazgos genéticos positivos del caso (genes con
      variante o mutación confirmada).
    - genes: símbolos de genes saneados (sin siglas de enfermedad).
    - discarded_symbols: siglas descartadas por ser enfermedades o abreviaturas
      clínicas, no genes.
    - negative_genetic_studies: estudios genéticos negativos mencionados en el
      caso (ej. "Panel CMT de 40 genes negativo").
    - annotations: anotaciones farmacogenómicas obtenidas de PharmGKB.
    - sources: estado de cada fuente consultada.
    """

    variants: list[str] = Field(default_factory=list)
    genetic_findings: list[str] = Field(default_factory=list)
    genes: list[str] = Field(default_factory=list)
    discarded_symbols: list[str] = Field(default_factory=list)
    negative_genetic_studies: list[str] = Field(default_factory=list)
    annotations: list[PharmacogenomicAnnotation] = Field(default_factory=list)
    sources: list[GenomicSource] = Field(default_factory=list)

    @property
    def has_genomic_findings(self) -> bool:
        """True si el caso tiene variantes o hallazgos genéticos positivos."""
        return bool(self.variants or self.genetic_findings)

    def to_prompt_block(self) -> str:
        """
        Serializa el contexto genómico como bloque de texto para incluir en el
        prompt del Agente 02.

        El bloque describe explícitamente qué hay y qué no hay para que el LLM
        no tenga que inferirlo.
        """
        lines: list[str] = ["=== CONTEXTO GENÓMICO ==="]

        if self.has_genomic_findings:
            if self.variants:
                lines.append(f"Variantes confirmadas: {', '.join(self.variants)}")
            if self.genetic_findings:
                lines.append(f"Hallazgos genéticos positivos: {', '.join(self.genetic_findings)}")
            if self.genes:
                lines.append(f"Genes mencionados (saneados): {', '.join(self.genes)}")
        else:
            lines.append(
                "No se reportan variantes genéticas ni hallazgos positivos en el caso."
            )
            if self.genes:
                lines.append(
                    f"Genes mencionados (sin variante confirmada): {', '.join(self.genes)}"
                )

        if self.negative_genetic_studies:
            lines.append(
                f"Estudios genéticos negativos: {'; '.join(self.negative_genetic_studies)}"
            )

        if self.discarded_symbols:
            lines.append(
                f"Símbolos descartados (enfermedades, no genes): "
                f"{', '.join(self.discarded_symbols)}"
            )

        if self.annotations:
            lines.append("Anotaciones farmacogenómicas (PharmGKB):")
            for ann in self.annotations:
                sig = f" — {ann.significance}" if ann.significance else ""
                lines.append(f"  • {ann.gene} / {ann.drug}{sig}")
        else:
            fuentes_farmaco = [
                s for s in self.sources if s.name == "PharmGKB"
            ]
            if fuentes_farmaco:
                st = fuentes_farmaco[0].status
                if st == GenomicSourceStatus.sin_resultados:
                    lines.append("PharmGKB: sin anotaciones para los genes del caso.")
                elif st == GenomicSourceStatus.no_disponible:
                    lines.append("PharmGKB: no disponible en esta corrida.")
                elif st == GenomicSourceStatus.no_consultada:
                    lines.append("PharmGKB: no consultada (sin genes en el caso).")

        lines.append("=========================")
        return "\n".join(lines)
