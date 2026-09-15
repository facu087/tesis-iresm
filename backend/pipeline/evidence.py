"""
Clasificación de evidencia EBM y priorización de hipótesis.

El `evidence_level` (I, II, III) que devuelve cada agente lo autodeclara el LLM,
y la verificación bibliográfica mostró que la mayoría de sus citas no resisten
el contraste contra PubMed. Este módulo acota ese nivel con reglas
deterministas (sin LLM y sin red), a partir de los veredictos que produce
`backend/pipeline/verification.py`:

1. **Tope por tipo de publicación.** Cada fuente VERIFICADA habilita un nivel
   máximo según los tipos que PubMed indexa para el artículo
   (Meta-Analysis → I, Observational Study → II, Case Reports → III, …).
2. **Nivel efectivo.** Es el nivel declarado por el agente, limitado por el
   mejor tope entre sus fuentes verificadas. Nunca sube: la verificación
   confirma que el PMID corresponde al título citado, no que el artículo
   sostenga la hipótesis. Sin fuentes verificadas, el nivel es III.
3. **Estado.** respaldada (≥1 fuente verificada), pendiente (la verificación
   no pudo concluir) o especulativa. Ninguna hipótesis se descarta.
4. **Orden.** estado → nivel efectivo → prioridad → fuentes verificadas →
   orden original.

Limitación conocida: el tipo "Systematic Review" existe en PubMed desde 2019.
Las revisiones sistemáticas anteriores suelen estar indexadas solo como
"Review" y topean en III, como una revisión narrativa.

Interfaz pensada para reutilizarse: el Agente 04 (Árbitro Verificador) puede
llamar `classify_hypothesis()` para su criterio de parada, y el Agente 06
(Sintetizador) `prioritize()` al reemplazar `report_builder.py`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from enum import Enum

from pydantic import BaseModel

from ..models.hypothesis import EvidenceLevel, Hypothesis, Priority
from .verification import SourceStatus, SourceVerification, source_key

# ── Tablas de tipos de publicación (en minúsculas) ────────────────────────────

LEVEL_I_PUBLICATION_TYPES: frozenset[str] = frozenset({
    "meta-analysis",
    "network meta-analysis",
    "systematic review",
    "randomized controlled trial",
})

LEVEL_II_PUBLICATION_TYPES: frozenset[str] = frozenset({
    "observational study",
    "clinical trial",
    "clinical trial, phase i",
    "clinical trial, phase ii",
    "clinical trial, phase iii",
    "clinical trial, phase iv",
    "controlled clinical trial",
    "pragmatic clinical trial",
    "comparative study",
    "multicenter study",
    # PubMed no informa el grado de recomendación de una guía: tope II.
    "practice guideline",
    "guideline",
})

LEVEL_III_PUBLICATION_TYPES: frozenset[str] = frozenset({
    "case reports",
    # Revisión narrativa = opinión de experto. Incluye, como limitación
    # conocida, las revisiones sistemáticas previas a 2019 indexadas así.
    "review",
    "scoping review",
    "letter",
    "editorial",
    "comment",
    "news",
    "consensus development conference",
})

# Una publicación retractada no sostiene más que nivel III, sea cual sea su diseño.
RETRACTED_PUBLICATION_TYPES: frozenset[str] = frozenset({
    "retracted publication",
    "retraction of publication",
})

# ── Pesos de orden ────────────────────────────────────────────────────────────

_LEVEL_RANK: dict[EvidenceLevel, int] = {
    EvidenceLevel.I: 0,
    EvidenceLevel.II: 1,
    EvidenceLevel.III: 2,
}
_PRIORITY_RANK: dict[Priority, int] = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


class HypothesisStatus(str, Enum):
    """Estado bibliográfico de una hipótesis. No existe "descartada"."""

    RESPALDADA = "respaldada"      # Al menos una fuente verificada contra PubMed
    PENDIENTE = "pendiente"        # La verificación no pudo concluir (red, sin ejecutar)
    ESPECULATIVA = "especulativa"  # Ninguna fuente resiste la verificación, o no cita fuentes


_STATUS_RANK: dict[HypothesisStatus, int] = {
    HypothesisStatus.RESPALDADA: 0,
    HypothesisStatus.PENDIENTE: 1,
    HypothesisStatus.ESPECULATIVA: 2,
}


class EvidenceAssessment(BaseModel):
    """Resultado de clasificar una hipótesis: nivel, estado y su explicación."""

    declared_level: EvidenceLevel
    ceiling: EvidenceLevel            # mejor tope entre fuentes verificadas (III si no hay)
    effective_level: EvidenceLevel
    status: HypothesisStatus
    verified_sources: int
    best_source_pmid: str | None = None
    best_source_types: list[str] = []
    note: str

    @property
    def capped(self) -> bool:
        """True si el nivel efectivo quedó por debajo del declarado por el agente."""
        return _LEVEL_RANK[self.effective_level] > _LEVEL_RANK[self.declared_level]


# ── Reglas ────────────────────────────────────────────────────────────────────

def _normalize_types(publication_types: Iterable[str]) -> set[str]:
    """Pasa los tipos a minúsculas y sin espacios circundantes, sin vacíos."""
    return {t.strip().lower() for t in publication_types if t and t.strip()}


def source_ceiling(publication_types: Iterable[str]) -> EvidenceLevel:
    """
    Devuelve el nivel de evidencia máximo que habilita un artículo verificado.

    Args:
        publication_types: Tipos de publicación que PubMed indexa para el artículo.

    Returns:
        I, II o III según la tabla de tipos. Una publicación retractada es III
        aunque tenga otros tipos; con varios tipos reconocidos gana el mejor; si
        ninguno está en la tabla (p. ej. solo "Journal Article") el tope es II,
        porque cohorte y caso-control se indexan como MeSH y no como tipo.
    """
    tipos = _normalize_types(publication_types)
    if tipos & RETRACTED_PUBLICATION_TYPES:
        return EvidenceLevel.III
    if tipos & LEVEL_I_PUBLICATION_TYPES:
        return EvidenceLevel.I
    if tipos & LEVEL_II_PUBLICATION_TYPES:
        return EvidenceLevel.II
    if tipos & LEVEL_III_PUBLICATION_TYPES:
        return EvidenceLevel.III
    return EvidenceLevel.II


def _worse(a: EvidenceLevel, b: EvidenceLevel) -> EvidenceLevel:
    """Devuelve el nivel de menor calidad entre dos (III es peor que I)."""
    return a if _LEVEL_RANK[a] >= _LEVEL_RANK[b] else b


def _describe_types(publication_types: list[str]) -> str:
    """Resume los tipos de publicación para la explicación del nivel."""
    tipos = _normalize_types(publication_types)
    if tipos & RETRACTED_PUBLICATION_TYPES:
        return "publicación retractada"
    reconocidos = [
        t for t in publication_types
        if t.strip().lower() in (
            LEVEL_I_PUBLICATION_TYPES | LEVEL_II_PUBLICATION_TYPES | LEVEL_III_PUBLICATION_TYPES
        )
    ]
    if reconocidos:
        return ", ".join(t.strip() for t in reconocidos)
    if publication_types:
        return f"sin diseño identificable ({', '.join(t.strip() for t in publication_types)})"
    return "sin tipo de publicación informado"


def _build_note(
    declared: EvidenceLevel,
    ceiling: EvidenceLevel,
    effective: EvidenceLevel,
    status: HypothesisStatus,
    best_pmid: str | None,
    best_types: list[str],
    has_sources: bool,
) -> str:
    """Arma la explicación en español de por qué la hipótesis quedó con su nivel."""
    declarado = "" if declared is EvidenceLevel.III else f" (el agente había declarado {declared.value})"

    if status is HypothesisStatus.PENDIENTE:
        return (
            "Verificación bibliográfica no disponible: el nivel queda en III hasta poder "
            f"confirmar las fuentes contra PubMed{declarado}."
        )
    if status is HypothesisStatus.ESPECULATIVA:
        if not has_sources:
            return f"La hipótesis no cita fuentes: nivel III{declarado}."
        return f"Ninguna fuente citada resistió la verificación contra PubMed: nivel III{declarado}."

    fuente = f"PMID {best_pmid}, {_describe_types(best_types)}"
    if effective is not declared:
        return (
            f"El agente declaró nivel {declared.value}; queda topeado en {effective.value} "
            f"porque la mejor fuente verificada ({fuente}) habilita como máximo "
            f"nivel {ceiling.value}."
        )
    return (
        f"Nivel {declared.value} declarado por el agente, compatible con la evidencia "
        f"verificada (mejor fuente: {fuente}; tope {ceiling.value})."
    )


def classify_hypothesis(
    hypothesis: Hypothesis,
    verifications: Mapping[str, SourceVerification],
) -> EvidenceAssessment:
    """
    Clasifica una hipótesis según los veredictos de la verificación bibliográfica.

    Solo cuentan los veredictos: los campos `verified` o `publication_types` que
    un LLM haya escrito en sus fuentes se ignoran.

    Args:
        hypothesis:    Hipótesis tal como la entregó el pipeline.
        verifications: Dict {source_key → SourceVerification} de
                       `verify_report_sources()`. Vacío si no se verificó.

    Returns:
        EvidenceAssessment con nivel declarado, tope, nivel efectivo, estado,
        cantidad de fuentes verificadas, mejor fuente y explicación.
    """
    veredictos: list[tuple[str | None, SourceVerification | None]] = []
    for source in hypothesis.sources:
        clave = source_key(source)
        veredictos.append((source.pmid, verifications.get(clave) if clave else None))

    verificadas = [v for _, v in veredictos if v is not None and v.status is SourceStatus.VERIFICADA]

    if verificadas:
        status = HypothesisStatus.RESPALDADA
    elif any(
        pmid and (v is None or v.status is SourceStatus.NO_VERIFICABLE)
        for pmid, v in veredictos
    ):
        status = HypothesisStatus.PENDIENTE
    else:
        status = HypothesisStatus.ESPECULATIVA

    ceiling = EvidenceLevel.III
    best: SourceVerification | None = None
    for veredicto in verificadas:
        tope = source_ceiling(veredicto.publication_types)
        if best is None or _LEVEL_RANK[tope] < _LEVEL_RANK[ceiling]:
            ceiling, best = tope, veredicto

    declared = hypothesis.evidence_level
    effective = _worse(declared, ceiling)
    best_pmid = best.pmid if best else None
    best_types = list(best.publication_types) if best else []

    return EvidenceAssessment(
        declared_level=declared,
        ceiling=ceiling,
        effective_level=effective,
        status=status,
        verified_sources=len(verificadas),
        best_source_pmid=best_pmid,
        best_source_types=best_types,
        note=_build_note(
            declared, ceiling, effective, status, best_pmid, best_types,
            has_sources=bool(hypothesis.sources),
        ),
    )


def prioritize(
    hypotheses: Sequence[Hypothesis],
    verifications: Mapping[str, SourceVerification],
) -> list[tuple[Hypothesis, EvidenceAssessment]]:
    """
    Clasifica y ordena las hipótesis para el reporte.

    Criterios, en orden de precedencia: estado (respaldada → pendiente →
    especulativa), nivel efectivo (I → III), prioridad declarada (HIGH → LOW),
    cantidad de fuentes verificadas (mayor primero) y orden original. Al ir el
    estado primero, las hipótesis de un mismo estado quedan contiguas.

    Args:
        hypotheses:    Hipótesis finales del pipeline, en el orden entregado.
        verifications: Veredictos de `verify_report_sources()`.

    Returns:
        Lista de pares (hipótesis, evaluación) ya ordenada. Ninguna se descarta.
    """
    evaluadas = [
        (indice, hipotesis, classify_hypothesis(hipotesis, verifications))
        for indice, hipotesis in enumerate(hypotheses)
    ]
    evaluadas.sort(
        key=lambda item: (
            _STATUS_RANK[item[2].status],
            _LEVEL_RANK[item[2].effective_level],
            _PRIORITY_RANK.get(item[1].priority, len(_PRIORITY_RANK)),
            -item[2].verified_sources,
            item[0],
        )
    )
    return [(hipotesis, evaluacion) for _, hipotesis, evaluacion in evaluadas]
