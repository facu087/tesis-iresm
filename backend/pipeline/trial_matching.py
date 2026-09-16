"""
Lógica determinista de la navegación de ensayos (Agente 05).

Todo lo que puede **quitar** un ensayo de la vista del médico vive acá y no en
el LLM: los filtros por edad y sexo, el saneamiento de los términos que salen
hacia APIs externas, la coincidencia exacta con Orphanet y el orden final del
resultado. Es la parte auditable, reproducible y testeable sin red.

El LLM solo traduce hipótesis a términos en inglés y etiqueta compatibilidad:
nunca excluye nada (ver `backend/agents/agent_05_trials.py`).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from ..models.case import ClinicalCase
from ..models.hypothesis import EvidenceLevel, Hypothesis, Priority
from ..models.trial import (
    ClinicalTrial,
    Compatibility,
    PatientDemographics,
    TrialCandidate,
    TrialNavigationInput,
)

# Cantidad máxima de hipótesis que se exploran en ClinicalTrials.gov.
MAX_CANDIDATES = 3

# Cantidad máxima de ensayos que llegan al reporte.
MAX_TRIALS = 10

# Estado de hipótesis que el Agente 04 (Árbitro) puede asignar y que excluye
# a la hipótesis de la exploración.
DISCARDED_STATUS = "descartada"

# Sede que el despliegue prefiere. Ordena el resultado, nunca lo filtra.
PREFERRED_COUNTRY = "argentina"


# ── Selección de candidatas ────────────────────────────────────────────────────

_PRIORITY_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
_EVIDENCE_ORDER = {EvidenceLevel.I: 0, EvidenceLevel.II: 1, EvidenceLevel.III: 2}


def select_candidates(
    hypotheses: list[Hypothesis],
    statuses: dict[str, str] | None = None,
) -> list[TrialCandidate]:
    """
    Elige las hipótesis a explorar: hasta `MAX_CANDIDATES`, sin descartadas.

    Args:
        hypotheses: Hipótesis del reporte final del debate o del consenso del Árbitro.
        statuses:   Mapa texto de hipótesis → estado bibliográfico, cuando existe.
                    Mismo criterio de clave por texto que usa `report_builder`.

    Returns:
        Candidatas ordenadas por prioridad (HIGH→LOW) y nivel de evidencia (I→III),
        sin repetir textos idénticos.
    """
    estados = statuses or {}
    candidatas: list[TrialCandidate] = []
    vistos: set[str] = set()

    for h in hypotheses:
        estado = estados.get(h.text)
        if estado == DISCARDED_STATUS:
            continue
        if h.text in vistos:
            continue
        vistos.add(h.text)
        candidatas.append(
            TrialCandidate(
                text=h.text,
                priority=h.priority,
                evidence_level=h.evidence_level,
                status=estado,
            )
        )

    candidatas.sort(
        key=lambda c: (
            _PRIORITY_ORDER.get(c.priority, 9),
            _EVIDENCE_ORDER.get(c.evidence_level, 9),
        )
    )
    return candidatas[:MAX_CANDIDATES]


# ── Saneamiento de términos ────────────────────────────────────────────────────

# Solo ASCII imprimible de un conjunto acotado, entre 2 y 80 caracteres.
_TERM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ,'()/+\-]{1,79}$")

_MAX_TERM_WORDS = 8

# Palabras que describen al paciente: si aparecen, el término se descarta entero.
_PATIENT_WORDS = frozenset({
    "patient", "patients", "year", "years", "yo", "old", "aged",
    "male", "female", "man", "woman", "men", "women",
})


def sanitize_term(term: str) -> str | None:
    """
    Devuelve el término si puede viajar a una API externa, o None si no.

    Descarta, nunca corrige: un término "arreglado" por código podría conservar
    justo la parte sensible. Ver design D7.
    """
    if not term:
        return None
    limpio = term.strip()
    if not _TERM_RE.match(limpio):
        return None
    palabras = limpio.split()
    if len(palabras) > _MAX_TERM_WORDS:
        return None
    for palabra in palabras:
        if palabra.strip(",'()/+-").lower() in _PATIENT_WORDS:
            return None
    return limpio


def sanitize_terms(terms: list[str], limit: int | None = None) -> list[str]:
    """Sanea una lista de términos, sin duplicados y conservando el orden."""
    salida: list[str] = []
    for term in terms:
        limpio = sanitize_term(term)
        if limpio and limpio not in salida:
            salida.append(limpio)
        if limit is not None and len(salida) >= limit:
            break
    return salida


# ── Demografía del paciente ────────────────────────────────────────────────────

# Patrones anclados al paciente, en orden de confianza decreciente.
_AGE_PATTERNS = (
    re.compile(r"(\d{1,3})\s*años\s+de\s+edad", re.IGNORECASE),
    re.compile(r"edad:?\s*(\d{1,3})", re.IGNORECASE),
    re.compile(
        r"(?:paciente|hombre|mujer|var[oó]n|masculino|femenino).{0,25}?(\d{1,3})\s*años",
        re.IGNORECASE | re.DOTALL,
    ),
)

# Una edad seguida de "de evolución" es el tiempo de enfermedad, no la del paciente.
_DURATION_RE = re.compile(r"^\s*(?:años\s*)?de\s+evoluci[oó]n", re.IGNORECASE)

_MALE_RE = re.compile(r"\b(?:masculino|var[oó]n|hombre)\b", re.IGNORECASE)
_FEMALE_RE = re.compile(r"\b(?:femenino|mujer)\b", re.IGNORECASE)

_MAX_HUMAN_AGE = 120


def parse_patient_demographics(profile: str) -> PatientDemographics:
    """
    Deduce edad y sexo del perfil PICO con reglas, sin usar el LLM.

    Conservador a propósito: ante una redacción que no reconoce devuelve None,
    y un dato faltante nunca excluye un ensayo. El error esperable es mostrar
    un ensayo de más, no esconder uno compatible (design D6).
    """
    if not profile:
        return PatientDemographics()

    edad: float | None = None
    for patron in _AGE_PATTERNS:
        for match in patron.finditer(profile):
            if _DURATION_RE.match(profile[match.end():]):
                continue
            valor = int(match.group(1))
            if 0 < valor <= _MAX_HUMAN_AGE:
                edad = float(valor)
                break
        if edad is not None:
            break

    es_masculino = bool(_MALE_RE.search(profile))
    es_femenino = bool(_FEMALE_RE.search(profile))
    if es_masculino and not es_femenino:
        sexo: str | None = "MALE"
    elif es_femenino and not es_masculino:
        sexo = "FEMALE"
    else:
        sexo = None

    return PatientDemographics(age_years=edad, sex=sexo)


# Unidades con las que ClinicalTrials.gov expresa los rangos etarios.
_AGE_UNITS = {
    "year": 1.0, "years": 1.0,
    "month": 1 / 12, "months": 1 / 12,
    "week": 1 / 52.1775, "weeks": 1 / 52.1775,
    "day": 1 / 365.25, "days": 1 / 365.25,
    "hour": 1 / 8766.0, "hours": 1 / 8766.0,
    "minute": 1 / 525960.0, "minutes": 1 / 525960.0,
}

_TRIAL_AGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([A-Za-z]+)\s*$")


def parse_trial_age(value: str | None) -> float | None:
    """
    Convierte una edad de ClinicalTrials.gov ("18 Years") a años.

    Devuelve None ante cualquier forma desconocida ("N/A", vacío, otra unidad):
    un rango que no se entiende no excluye a nadie.
    """
    if not value:
        return None
    match = _TRIAL_AGE_RE.match(value)
    if not match:
        return None
    factor = _AGE_UNITS.get(match.group(2).lower())
    if factor is None:
        return None
    return float(match.group(1)) * factor


# ── Filtros duros ──────────────────────────────────────────────────────────────

@dataclass
class FilterCounts:
    """Cuántos ensayos se excluyeron y por qué motivo."""

    por_edad: int = 0
    por_sexo: int = 0


def exclusion_reason(
    trial: ClinicalTrial, demographics: PatientDemographics
) -> str | None:
    """
    Devuelve "edad", "sexo" o None si el ensayo se conserva.

    Solo excluye cuando el dato del paciente y el criterio del ensayo se conocen
    y son incompatibles. Si alguno falta o no se puede interpretar, se conserva.
    """
    if demographics.age_years is not None:
        minima = parse_trial_age(trial.min_age)
        maxima = parse_trial_age(trial.max_age)
        if minima is not None and demographics.age_years < minima:
            return "edad"
        if maxima is not None and demographics.age_years > maxima:
            return "edad"

    if demographics.sex is not None and trial.sex:
        sexo_ensayo = trial.sex.strip().upper()
        if sexo_ensayo in ("MALE", "FEMALE") and sexo_ensayo != demographics.sex:
            return "sexo"

    return None


def apply_hard_filters(
    trials: list[ClinicalTrial], demographics: PatientDemographics
) -> tuple[list[ClinicalTrial], FilterCounts]:
    """Aplica los filtros duros y devuelve los ensayos que quedan y el conteo."""
    conteo = FilterCounts()
    conservados: list[ClinicalTrial] = []
    for trial in trials:
        motivo = exclusion_reason(trial, demographics)
        if motivo == "edad":
            conteo.por_edad += 1
        elif motivo == "sexo":
            conteo.por_sexo += 1
        else:
            conservados.append(trial)
    return conservados, conteo


# ── Coincidencia con Orphanet ──────────────────────────────────────────────────

def normalize_words(text: str) -> frozenset[str]:
    """
    Reduce un texto a su conjunto de palabras normalizadas.

    Minúsculas, sin acentos, puntuación y guiones convertidos en espacios.
    """
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    limpio = "".join(c.lower() if c.isalnum() else " " for c in sin_acentos)
    return frozenset(limpio.split())


def normalize_disease_name(name: str) -> frozenset[str]:
    """
    Normaliza un nombre de enfermedad para compararlo con Orphanet.

    El orden de las palabras no importa, pero el conjunto tiene que ser idéntico.
    """
    return normalize_words(name)


def names_match(term: str, preferred_term: str) -> bool:
    """
    True solo ante coincidencia exacta normalizada.

    La coincidencia por inclusión marca una neuropatía axonal del adulto como
    enfermedad neonatal letal (medido contra la API real): etiquetar mal una
    hipótesis es peor que no marcarla (design D8).
    """
    normalizado = normalize_disease_name(term)
    if not normalizado:
        return False
    return normalizado == normalize_disease_name(preferred_term)


# ── Unificación y orden de los ensayos ─────────────────────────────────────────

@dataclass
class TrialHit:
    """Un ensayo tal como lo devolvió una consulta puntual."""

    trial: ClinicalTrial
    term: str
    hypothesis: str | None = None


@dataclass
class _Accumulated:
    trial: ClinicalTrial
    terms: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)


def merge_trials(hits: list[TrialHit], limit: int = MAX_TRIALS) -> list[ClinicalTrial]:
    """
    Unifica los ensayos por NCT ID conservando el orden de descubrimiento.

    Cada ensayo registra en `matched_terms` los términos que lo encontraron y en
    `related_hypotheses` los textos de las hipótesis cuyas consultas lo trajeron
    (vacío si solo lo trajo la búsqueda base).
    """
    acumulados: dict[str, _Accumulated] = {}
    orden: list[str] = []

    for hit in hits:
        nct = hit.trial.nct_id
        if nct not in acumulados:
            acumulados[nct] = _Accumulated(trial=hit.trial)
            orden.append(nct)
        acumulado = acumulados[nct]
        if hit.term and hit.term not in acumulado.terms:
            acumulado.terms.append(hit.term)
        if hit.hypothesis and hit.hypothesis not in acumulado.hypotheses:
            acumulado.hypotheses.append(hit.hypothesis)

    unificados: list[ClinicalTrial] = []
    for nct in orden[:limit]:
        acumulado = acumulados[nct]
        unificados.append(
            acumulado.trial.model_copy(
                update={
                    "matched_terms": acumulado.terms,
                    "related_hypotheses": acumulado.hypotheses,
                }
            )
        )
    return unificados


_COMPATIBILITY_ORDER = {
    Compatibility.ALTA.value: 0,
    Compatibility.MEDIA.value: 1,
    Compatibility.BAJA.value: 2,
    Compatibility.SIN_EVALUAR.value: 3,
}


def has_preferred_location(trial: ClinicalTrial) -> bool:
    """True si el ensayo tiene una sede en Argentina (comparación normalizada)."""
    return any(PREFERRED_COUNTRY in normalize_words(pais) for pais in trial.locations)


def sort_trials(trials: list[ClinicalTrial]) -> list[ClinicalTrial]:
    """
    Ordena: compatibilidad → sede en Argentina → ya reclutando → descubrimiento.

    La sede y el estado de reclutamiento ordenan y nunca excluyen. La
    compatibilidad va primero porque es el criterio clínico: un ensayo local
    poco compatible arriba de uno muy compatible del exterior invierte el
    criterio por uno logístico (design D15).
    """
    return sorted(
        trials,
        key=lambda t: (
            _COMPATIBILITY_ORDER.get(t.compatibility, 3),
            0 if has_preferred_location(t) else 1,
            0 if t.status == "RECRUITING" else 1,
        ),
    )


# ── Adaptador de entrada ───────────────────────────────────────────────────────

def _build_eligibility_profile(case: ClinicalCase) -> str:
    """
    Arma el perfil que se le manda al LLM para evaluar compatibilidad.

    Solo campos de la síntesis PICO: nunca `raw_text` ni `clinical_narrative`,
    que arrastran el documento original completo.
    """
    if case.pico is None:
        return ""

    pico = case.pico
    lineas: list[str] = []
    if pico.patient_profile:
        lineas.append(f"Perfil: {pico.patient_profile}")
    if pico.chief_complaint:
        lineas.append(f"Motivo de consulta: {pico.chief_complaint}")
    if pico.disease_duration:
        lineas.append(f"Tiempo de evolución: {pico.disease_duration}")
    if pico.relevant_history:
        lineas.append(f"Antecedentes: {', '.join(pico.relevant_history)}")
    if pico.negative_findings:
        lineas.append(f"Estudios negativos: {', '.join(pico.negative_findings)}")
    if pico.current_treatments:
        lineas.append(f"Tratamientos actuales: {', '.join(pico.current_treatments)}")
    if pico.genetic_findings:
        lineas.append(f"Hallazgos genéticos: {', '.join(pico.genetic_findings)}")
    return "\n".join(lineas)


def build_navigation_input(
    case: ClinicalCase,
    hypotheses: list[Hypothesis],
    statuses: dict[str, str] | None = None,
) -> TrialNavigationInput:
    """
    Único lugar que sabe de dónde vienen las hipótesis del Agente 05.

    Hoy el router lo llama con las hipótesis del reporte final del debate;
    cuando exista el Agente 04 se lo llama con su consenso y el mapa de estados,
    sin tocar el agente (design D3).

    Args:
        case:       ClinicalCase con la síntesis PICO y los biomarcadores.
        hypotheses: Hipótesis a explorar.
        statuses:   Mapa texto de hipótesis → estado bibliográfico, opcional.

    Returns:
        TrialNavigationInput con términos ya saneados y la demografía deducida.
    """
    condition_en = ""
    if case.pico and case.pico.condition_en:
        condition_en = sanitize_term(case.pico.condition_en) or ""

    biomarcadores: list[str] = []
    if case.biomarkers is not None:
        crudos = (
            case.biomarkers.genes
            + case.biomarkers.antibodies
            + case.biomarkers.drugs
        )
        biomarcadores = sanitize_terms(crudos, limit=5)

    perfil = case.pico.patient_profile if case.pico else ""

    return TrialNavigationInput(
        condition_en=condition_en,
        biomarker_terms=biomarcadores,
        demographics=parse_patient_demographics(perfil),
        eligibility_profile=_build_eligibility_profile(case),
        candidates=select_candidates(hypotheses, statuses),
    )
