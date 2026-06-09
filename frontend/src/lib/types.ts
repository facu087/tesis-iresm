/**
 * Tipos TypeScript que espejean los modelos Pydantic del backend.
 * Fuente de verdad: backend/api/schemas.py y backend/models/
 */

export type Priority = "HIGH" | "MEDIUM" | "LOW";
export type EvidenceLevel = "I" | "II" | "III";

export interface Source {
  pmid?: string;
  title: string;
  journal?: string;
  year?: number;
  url?: string;
}

export interface RankedHypothesis {
  rank: number;
  text: string;
  priority: Priority;
  evidence_level: EvidenceLevel;
  rationale: string;
  supporting_agents: string[];
  sources: Source[];
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

export interface StructuredReport {
  metadata: ReportMetadata;
  case_summary: CaseSummarySection;
  hypotheses: RankedHypothesis[];
  debate_summary: DebateSummary;
  clinical_trials: ClinicalTrial[];
  bibliography: Source[];
}

/** Error estructurado que devuelve FastAPI */
export interface ApiError {
  detail: string | { msg: string; type: string }[];
}
