import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DebateTab } from "./CaseDebateTabs";
import type { AgentProviderInfo, DebateSummary } from "@/lib/types";

const debate: DebateSummary = {
  rounds_completed: 4,
  total_critiques: 6,
  consensus_reached: true,
  divergences: [],
};

describe("DebateTab — models that answered (multi-provider)", () => {
  it("shows the provider and model of each agent, and the fallback reason", () => {
    const providers: AgentProviderInfo[] = [
      { agent_id: "01", agent_name: "Analista de Literatura", provider: "anthropic",
        model: "claude-opus-5-5", fallback_reason: null },
      { agent_id: "03", agent_name: "Consultor Clínico", provider: "groq",
        model: "openai/gpt-oss-120b", fallback_reason: "clave_faltante" },
    ];
    render(<DebateTab debate={debate} providers={providers} />);
    expect(screen.getByText("Modelos que respondieron")).toBeInTheDocument();
    expect(screen.getByText("claude-opus-5-5")).toBeInTheDocument();
    expect(screen.getByText(/Anthropic/)).toBeInTheDocument();
    expect(screen.getByText("openai/gpt-oss-120b")).toBeInTheDocument();
    expect(screen.getByText(/faltaba la clave del proveedor asignado/)).toBeInTheDocument();
  });

  it("leaves the section out for a report older than the field", () => {
    render(<DebateTab debate={debate} />);
    expect(screen.queryByText("Modelos que respondieron")).not.toBeInTheDocument();
    render(<DebateTab debate={debate} providers={null} />);
    expect(screen.queryByText("Modelos que respondieron")).not.toBeInTheDocument();
  });
});
