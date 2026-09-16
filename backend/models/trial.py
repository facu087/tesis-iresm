"""
Modelos de datos para ensayos clínicos obtenidos de ClinicalTrials.gov y para
la navegación de ensayos del Agente 05 (Navegador de Ensayos).

Los campos de compatibilidad que suma `ClinicalTrial` son **aditivos**: un JSON
generado antes del Agente 05 sigue validando y queda en `sin_evaluar`, igual
que el precedente de `Source.verified` con la verificación bibliográfica.

La compatibilidad es orientativa: la elegibilidad real la determina el equipo
investigador de cada ensayo. NEXUS no afirma que un paciente sea elegible.
"""

from enum import Enum

from pydantic import BaseModel

from .hypothesis import EvidenceLevel, Priority


class Compatibility(str, Enum):
    """Etiqueta orientativa de compatibilidad de un ensayo con el perfil."""

    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"
    SIN_EVALUAR = "sin_evaluar"


class ApiStatus(str, Enum):
    """Resultado agregado de consultar una API externa durante la navegación."""

    OK = "ok"                        # Todas las consultas respondieron
    PARCIAL = "parcial"              # Algunas respondieron y otras fallaron
    NO_DISPONIBLE = "no_disponible"  # Ninguna consulta respondió
    SIN_CONSULTA = "sin_consulta"    # No hubo términos válidos para consultar


class StepStatus(str, Enum):
    """Resultado de un paso del agente que depende del LLM."""

    OK = "ok"                          # El LLM respondió y su salida se usó
    FALLBACK = "fallback"              # Falló: se siguió sin esa información
    SIN_CANDIDATAS = "sin_candidatas"  # No había hipótesis que planificar
    SIN_ENSAYOS = "sin_ensayos"        # No había ensayos que evaluar


class ClinicalTrial(BaseModel):
    nct_id: str                          # Identificador NCT (ej: "NCT04123456")
    title: str                           # Título breve del ensayo
    status: str                          # Estado (RECRUITING, NOT_YET_RECRUITING, etc.)
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

    # ── Agente 05 — campos aditivos, con default para los reportes previos ────
    # Etiqueta orientativa: alta | media | baja | sin_evaluar.
    compatibility: str = Compatibility.SIN_EVALUAR.value
    # Fundamento breve en español de la etiqueta anterior (None si no se evaluó).
    compatibility_rationale: str | None = None
    # Criterios que el médico responsable debe verificar antes de derivar.
    criteria_to_verify: list[str] = []
    # Textos de las hipótesis cuyas consultas trajeron este ensayo.
    related_hypotheses: list[str] = []
    # Términos en inglés con los que se encontró el ensayo.
    matched_terms: list[str] = []

    def summary_line(self) -> str:
        """Línea compacta para mostrar en reportes."""
        phase_str = f" | {self.phase}" if self.phase and self.phase != "NA" else ""
        return f"{self.nct_id}{phase_str} — {self.title[:80]}"


class RareDiseaseMatch(BaseModel):
    """
    Hipótesis que corresponde a una enfermedad rara catalogada en Orphanet.

    Nunca es un diagnóstico del paciente: dice que la *hipótesis* coincide de
    forma exacta con el nombre preferido de una entidad clínica de Orphanet.
    """

    orpha_code: str        # Código ORPHA (ej: "271861")
    name: str              # Nombre preferido en Orphanet
    url: str               # Ficha en orpha.net
    hypothesis: str        # Texto de la hipótesis marcada
    matched_term: str      # Término en inglés que coincidió


class TrialSearchSummary(BaseModel):
    """
    Qué se consultó, qué falló y qué se excluyó durante la navegación.

    Permite que el reporte distinga "no hay ensayos" de "no se pudo consultar".
    Los nombres van en español, como `VerificationSummary`.
    """

    estado_clinicaltrials: str = ApiStatus.SIN_CONSULTA.value
    estado_orphanet: str = ApiStatus.SIN_CONSULTA.value
    planificacion: str = StepStatus.SIN_CANDIDATAS.value
    evaluacion: str = StepStatus.SIN_ENSAYOS.value
    terminos_consultados: list[str] = []   # Términos en inglés enviados a las APIs
    encontrados: int = 0                   # Ensayos únicos antes de los filtros duros
    excluidos_por_edad: int = 0
    excluidos_por_sexo: int = 0
    evaluaciones_descartadas: int = 0      # NCT IDs que el LLM inventó


class TrialCandidate(BaseModel):
    """
    Hipótesis a explorar en ClinicalTrials.gov.

    Contrato neutral: no sabe si viene del reporte final del debate o del
    consenso del Agente 04. `status` es el estado bibliográfico de la hipótesis
    cuando existe ("respaldada", "pendiente", "especulativa", "descartada").
    """

    text: str
    priority: Priority
    evidence_level: EvidenceLevel
    status: str | None = None


class PatientDemographics(BaseModel):
    """
    Edad y sexo del paciente, deducidos por reglas del perfil PICO.

    Solo se usan para filtrar localmente: nunca viajan a una API externa.
    `None` significa "no se pudo interpretar" y nunca excluye un ensayo.
    """

    age_years: float | None = None
    sex: str | None = None  # "MALE" | "FEMALE" | None


class TrialNavigationInput(BaseModel):
    """
    Entrada del Agente 05, armada por `pipeline/trial_matching.build_navigation_input`.

    `eligibility_profile` se arma solo con campos de la síntesis PICO: nunca
    incluye `raw_text` ni la narrativa clínica completa.
    """

    condition_en: str = ""
    biomarker_terms: list[str] = []
    demographics: PatientDemographics = PatientDemographics()
    eligibility_profile: str = ""
    candidates: list[TrialCandidate] = []


class TrialNavigationResult(BaseModel):
    """Salida del Agente 05: ensayos ordenados, enfermedades raras y estado."""

    trials: list[ClinicalTrial] = []
    rare_diseases: list[RareDiseaseMatch] = []
    summary: TrialSearchSummary = TrialSearchSummary()
