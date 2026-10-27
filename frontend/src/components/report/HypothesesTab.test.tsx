import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HipotesisTab } from "./HypothesesTab";
import { makeReport } from "@/test/fixtures";
import type { RankedHypothesis } from "@/lib/types";

function hypothesis(overrides: Partial<RankedHypothesis>): RankedHypothesis {
  return { ...makeReport().hypotheses[0], ...overrides };
}

describe("HipotesisTab evidence level", () => {
  it("says the level was not declared when the agent gave no valid level", () => {
    render(
      <HipotesisTab
        hypotheses={[hypothesis({ evidence_level_defaulted: true, declared_evidence_level: null })]}
      />,
    );
    expect(screen.getByText(/no declarado por el agente/)).toBeInTheDocument();
  });

  it("does not mark a level the agent declared as III", () => {
    render(<HipotesisTab hypotheses={[hypothesis({ declared_evidence_level: "III" })]} />);
    expect(screen.queryByText(/no declarado por el agente/)).not.toBeInTheDocument();
  });

  it("still shows the declared level when it was capped", () => {
    render(
      <HipotesisTab
        hypotheses={[hypothesis({ evidence_level: "II", declared_evidence_level: "I" })]}
      />,
    );
    expect(screen.getByText(/el agente declaró/)).toBeInTheDocument();
  });
});
