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

export type HypothesisStatus = "respaldada" | "especulativa";

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
}

export interface RankedHypothesis {
  rank: number;
  text: string;
  priority: Priority;
  evidence_level: EvidenceLevel;
  rationale: string;
  supporting_agents: string[];
  sources: Source[];
  status: HypothesisStatus;
  verified_sources: number;
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
}

export interface StructuredReport {
  metadata: ReportMetadata;
  case_summary: CaseSummarySection;
  hypotheses: RankedHypothesis[];
  debate_summary: DebateSummary;
  clinical_trials: ClinicalTrial[];
  bibliography: Source[];
  verification?: VerificationSummary;
}

/** Error estructurado que devuelve FastAPI */
export interface ApiError {
  detail: string | { msg: string; type: string }[];
}
