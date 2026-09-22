/**
 * Tipos TypeScript que espejean los modelos Pydantic del backend.
 * Fuente de verdad: backend/api/schemas.py y backend/models/
 */

export type Priority = "HIGH" | "MEDIUM" | "LOW";
export type EvidenceLevel = "I" | "II" | "III";

/** Veredicto de la verificación bibliográfica (Agente 04). */
export type VerificationStatus =
  | "verificada"      // El PMID existe y el título coincide
  | "discordante"     // Existe pero corresponde a otro artículo
  | "inexistente"     // No está en PubMed
  | "sin_pmid"        // La fuente no declaró PMID
  | "no_verificable"; // Falló la consulta (red, rate limit)

/**
 * Estado bibliográfico de la hipótesis (backend/pipeline/evidence.py).
 * Ninguna se descarta: "pendiente" = la verificación no pudo concluir.
 */
export type HypothesisStatus = "respaldada" | "pendiente" | "especulativa";

export interface Source {
  pmid?: string;
  title: string;
  journal?: string;
  year?: number;
  url?: string;
  verified?: boolean | null;
  verification_status?: VerificationStatus | null;
  /** Título real en PubMed, cuando no coincide con el citado. */
  actual_title?: string | null;
  /** Tipos de publicación indexados en PubMed (solo fuentes verificadas). */
  publication_types?: string[];
}

export interface RankedHypothesis {
  rank: number;
  text: string;
  priority: Priority;
  /** Nivel EBM efectivo: el declarado por el agente, topeado por la evidencia verificada. */
  evidence_level: EvidenceLevel;
  rationale: string;
  supporting_agents: string[];
  sources: Source[];
  status: HypothesisStatus;
  verified_sources: number;
  /** Nivel que declaró el agente (puede ser mejor que el efectivo). */
  declared_evidence_level?: EvidenceLevel | null;
  /** Explicación de por qué la hipótesis quedó con su nivel efectivo. */
  evidence_note?: string;

  /* Consenso del Árbitro (Agente 04). Opcionales: un reporte anterior al
     Árbitro llega sin ellos y la vista lo renderiza como antes. */
  /** Agentes que objetaron la hipótesis y no incorporaron la crítica. */
  refuting_agents?: string[];
  contradictions?: Contradiction[];
  /** Veredicto del Árbitro, en lenguaje llano. */
  arbiter_note?: string;
  recitation?: RecitationOutcome;
}

/** Objeción de peso que quedó sin resolver al cerrar el debate. */
export interface Contradiction {
  from_agent_name: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  critique_text: string;
  alternative?: string | null;
}

/** Qué pasó con la hipótesis en la Ronda 5 de recitación. */
export type RecitationOutcome =
  | "no_aplica"
  | "mejorada"
  | "sin_cambio"
  | "fallida";

/** Resultado de la Ronda 5: se les pidió volver a citar sobre literatura real. */
export interface RecitationSummary {
  executed: boolean;
  recited: number;
  improved: number;
  rejected_pmids: number;
  failed_agents: string[];
}

/**
 * Resumen del arbitraje (Agente 04).
 *
 * `rag_overlap` sobre `cited_sources` es el número que justifica que el Árbitro
 * exista: cuántas de las citas de los agentes salieron de la literatura que el
 * RAG les había puesto en el prompt.
 */
export interface ArbitrationSummary {
  status: "ok" | "degradado" | "sin_hipotesis";
  input_hypotheses: number;
  consensus_hypotheses: number;
  contradictions: number;
  cited_sources: number;
  rag_overlap: number;
  retrieved_articles: number;
  discarded_references: number;
  recitation: RecitationSummary;
}

export interface CaseSummarySection {
  narrative: string;
  patient_profile?: string;
  chief_complaint?: string;
  disease_duration?: string;
  current_treatments?: string[];
  relevant_history?: string[];
  procedures_done?: string[];
}

export interface DebateSummary {
  rounds_completed: number;
  total_critiques: number;
  divergences: string[];
  consensus_reached: boolean;
}

/**
 * Etiqueta orientativa de compatibilidad (Agente 05).
 * No afirma elegibilidad: la determina el equipo investigador del ensayo.
 */
export type Compatibility = "alta" | "media" | "baja" | "sin_evaluar";

/** Resultado de consultar una API externa durante la navegación de ensayos. */
export type ApiStatus = "ok" | "parcial" | "no_disponible" | "sin_consulta";

/** Resultado de un paso del Agente 05 que depende del LLM. */
export type StepStatus = "ok" | "fallback" | "sin_candidatas" | "sin_ensayos";

export interface ClinicalTrial {
  nct_id: string;
  title: string;
  status: string;
  brief_summary: string;
  conditions: string[];
  phase?: string;
  sponsor?: string;
  start_date?: string;
  completion_date?: string;
  eligibility_criteria?: string;
  min_age?: string;
  max_age?: string;
  sex?: string;
  locations: string[];
  url: string;
  /* Agente 05 — campos opcionales: un reporte previo no los trae. */
  compatibility?: Compatibility;
  compatibility_rationale?: string | null;
  criteria_to_verify?: string[];
  related_hypotheses?: string[];
  matched_terms?: string[];
}

/**
 * Hipótesis que corresponde a una enfermedad rara catalogada en Orphanet.
 * Nunca es un diagnóstico del paciente.
 */
export interface RareDiseaseMatch {
  orpha_code: string;
  name: string;
  url: string;
  hypothesis: string;
  matched_term: string;
}

/** Qué se consultó, qué falló y qué se excluyó durante la navegación. */
export interface TrialSearchSummary {
  estado_clinicaltrials: ApiStatus;
  estado_orphanet: ApiStatus;
  planificacion: StepStatus;
  evaluacion: StepStatus;
  terminos_consultados: string[];
  encontrados: number;
  excluidos_por_edad: number;
  excluidos_por_sexo: number;
  evaluaciones_descartadas: number;
}

export interface ReportMetadata {
  generated_at: string;
  nexus_version: string;
  processing_time_seconds: number;
  disclaimer: string;
}

/** Recuento de la verificación bibliográfica sobre todo el reporte. */
export interface VerificationSummary {
  total_fuentes: number;
  verificadas: number;
  discordantes: number;
  inexistentes: number;
  sin_pmid: number;
  no_verificables: number;
  hipotesis_respaldadas: number;
  hipotesis_especulativas: number;
  /** Respaldadas + pendientes + especulativas = total de hipótesis. */
  hipotesis_pendientes?: number;
  /** Hipótesis cuyo nivel efectivo quedó por debajo del declarado. */
  hipotesis_topeadas?: number;
}

export interface StructuredReport {
  metadata: ReportMetadata;
  case_summary: CaseSummarySection;
  hypotheses: RankedHypothesis[];
  debate_summary: DebateSummary;
  clinical_trials: ClinicalTrial[];
  bibliography: Source[];
  verification?: VerificationSummary;
  /* Agente 05. `trial_search` nulo o ausente = reporte anterior al agente:
     la vista renderiza los ensayos como antes. */
  rare_diseases?: RareDiseaseMatch[];
  trial_search?: TrialSearchSummary | null;
  /* Agente 04. Nulo o ausente = reporte anterior al Árbitro: las hipótesis
     vienen del debate sin consolidar y la vista no muestra el consenso. */
  arbitration?: ArbitrationSummary | null;
}

/** Error estructurado que devuelve FastAPI */
export interface ApiError {
  detail: string | { msg: string; type: string }[];
}
