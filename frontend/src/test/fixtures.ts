import type { StructuredReport } from "@/lib/types";

/** Smallest report the `/report` view renders: one hypothesis, no trials. */
export function makeReport(): StructuredReport {
  return {
    metadata: {
      generated_at: "2026-10-06T12:00:00Z",
      nexus_version: "0.4.0",
      processing_time_seconds: 42.5,
      disclaimer: "Test disclaimer.",
    },
    case_summary: { narrative: "Test narrative." },
    hypotheses: [
      {
        rank: 1,
        text: "Test hypothesis",
        priority: "HIGH",
        evidence_level: "III",
        rationale: "Test rationale.",
        supporting_agents: ["01"],
        sources: [],
        status: "especulativa",
        verified_sources: 0,
      },
    ],
    debate_summary: {
      rounds_completed: 4,
      total_critiques: 0,
      divergences: [],
      consensus_reached: true,
    },
    clinical_trials: [],
    bibliography: [],
  };
}
