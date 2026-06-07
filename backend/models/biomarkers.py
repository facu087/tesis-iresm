"""
Modelo de datos para el perfil de biomarcadores y historial terapéutico.
"""

from pydantic import BaseModel


class BiomarkerProfile(BaseModel):
    # Entidades genómicas
    genes: list[str] = []               # Genes mencionados (ej: TTR, PMP22)
    genetic_variants: list[str] = []    # Variantes (ej: p.Val30Met, c.148G>A)

    # Entidades inmunológicas
    antibodies: list[str] = []          # Anticuerpos (ej: anti-Hu, anti-gangliósido GM1)

    # Biomarcadores de laboratorio
    lab_biomarkers: list[str] = []      # Marcadores séricos/LCR (ej: vitamina B12, HbA1c)

    # Vías y síndromes
    pathways: list[str] = []            # Diagnósticos/síndromes mencionados o descartados

    # Historial terapéutico
    drugs: list[str] = []              # Fármacos (nombre INN)
    procedures: list[str] = []         # Procedimientos diagnósticos
    surgeries: list[str] = []          # Cirugías

    def is_empty(self) -> bool:
        return not any([
            self.genes, self.genetic_variants, self.antibodies,
            self.lab_biomarkers, self.pathways, self.drugs, self.procedures
        ])

    def summary(self) -> str:
        """Resumen compacto para logs y debugging."""
        parts = []
        if self.genes:
            parts.append(f"genes={self.genes}")
        if self.antibodies:
            parts.append(f"anticuerpos={len(self.antibodies)}")
        if self.lab_biomarkers:
            parts.append(f"lab={len(self.lab_biomarkers)}")
        if self.drugs:
            parts.append(f"fármacos={self.drugs}")
        if self.procedures:
            parts.append(f"procedimientos={len(self.procedures)}")
        return " | ".join(parts) if parts else "sin entidades identificadas"
