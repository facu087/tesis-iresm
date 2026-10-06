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


class ClinVarStatus(str, Enum):
    """Resultado de consultar una variante en ClinVar."""

    encontrada = "encontrada"
    sin_resultados = "sin_resultados"
    ambigua = "ambigua"
    no_disponible = "no_disponible"


class VariantClassification(BaseModel):
    """Clasificación germinal de ClinVar para una variante del caso."""

    gene: str
    variant: str
    status: ClinVarStatus
    classification: str = ""
    review_status: str = ""
    last_evaluated: str = ""
    accession: str = ""
    url: str = ""
    title: str = ""
    candidates: int = 0
    detail: str = ""


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
    - clinvar: clasificación de ClinVar de cada variante consultada.
    - sources: estado de cada fuente consultada.
    """

    variants: list[str] = Field(default_factory=list)
    genetic_findings: list[str] = Field(default_factory=list)
    genes: list[str] = Field(default_factory=list)
    discarded_symbols: list[str] = Field(default_factory=list)
    negative_genetic_studies: list[str] = Field(default_factory=list)
    annotations: list[PharmacogenomicAnnotation] = Field(default_factory=list)
    clinvar: list[VariantClassification] = Field(default_factory=list)
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

        if self.clinvar:
            lines.append("Clasificación de variantes (ClinVar):")
            for c in self.clinvar:
                if c.status == ClinVarStatus.encontrada:
                    lines.append(
                        f"  • {c.gene} {c.variant}: {c.classification} "
                        f"({c.review_status}; {c.accession})"
                    )
                elif c.status == ClinVarStatus.ambigua:
                    lines.append(
                        f"  • {c.gene} {c.variant}: ambigua — {c.candidates} registros sin "
                        "coincidencia exacta; no usar ninguna clasificación de ClinVar"
                    )
                elif c.status == ClinVarStatus.sin_resultados:
                    lines.append(f"  • {c.gene} {c.variant}: sin registros en ClinVar")
                else:
                    lines.append(f"  • {c.gene} {c.variant}: ClinVar no disponible")
        else:
            clinvar_src = next((s for s in self.sources if s.name == "ClinVar"), None)
            if clinvar_src is not None and clinvar_src.status == GenomicSourceStatus.no_consultada:
                lines.append("ClinVar: no consultada (sin variantes con gen identificable).")

        lines.append("=========================")
        return "\n".join(lines)
