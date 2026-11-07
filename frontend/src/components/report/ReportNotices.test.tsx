import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FRASES_CAUSA, VerificationBanner } from "./ReportNotices";
import type { CausaFallo, VerificationSummary } from "@/lib/types";

function summary(overrides: Partial<VerificationSummary>): VerificationSummary {
  return {
    total_fuentes: 4,
    verificadas: 0,
    discordantes: 0,
    inexistentes: 0,
    sin_pmid: 0,
    no_verificables: 4,
    hipotesis_respaldadas: 0,
    hipotesis_especulativas: 0,
    hipotesis_pendientes: 2,
    ...overrides,
  };
}

/** The positive tone is the only one painted with the accent background. */
function looksPositive(container: HTMLElement): boolean {
  return container.querySelector(".bg-accent\\/10") !== null;
}

describe("VerificationBanner — verification that did not run (card #91)", () => {
  it("says the check could not run, names a misconfigured key and is not shown as a success", () => {
    const { container } = render(
      <VerificationBanner v={summary({ estado: "no_disponible", causa: "configuracion" })} />,
    );
    expect(screen.getByText(/no se pudo hacer/)).toBeInTheDocument();
    expect(screen.getByText(/posible clave de PubMed mal configurada/)).toBeInTheDocument();
    expect(screen.queryByText(/fallo de red/)).not.toBeInTheDocument();
    expect(looksPositive(container)).toBe(false);
  });

  it("says a partial check is incomplete and how many references were not consulted", () => {
    render(
      <VerificationBanner
        v={summary({ estado: "parcial", causa: "red", verificadas: 1, no_verificables: 3 })}
      />,
    );
    expect(screen.getByText(/quedó incompleta/)).toBeInTheDocument();
    expect(screen.getByText(/3 referencias no se pudieron consultar/)).toBeInTheDocument();
  });

  it("shows no incomplete notice when the check is complete", () => {
    const { container } = render(
      <VerificationBanner
        v={summary({ estado: "completa", verificadas: 4, no_verificables: 0, hipotesis_pendientes: 0 })}
      />,
    );
    expect(screen.queryByText(/no se pudo hacer/)).not.toBeInTheDocument();
    expect(screen.queryByText(/quedó incompleta/)).not.toBeInTheDocument();
    expect(looksPositive(container)).toBe(true);
  });

  it("does not claim a cause on a report saved before the change", () => {
    render(<VerificationBanner v={summary({ verificadas: 1, no_verificables: 3 })} />);
    expect(screen.getByText(/3 no se pudieron consultar/)).toBeInTheDocument();
    expect(screen.queryByText(/fallo de red/)).not.toBeInTheDocument();
    expect(screen.queryByText(/no se pudo hacer/)).not.toBeInTheDocument();
  });

  it("has a plain-language phrase for every cause", () => {
    const causas: CausaFallo[] = [
      "red",
      "limite_velocidad",
      "configuracion",
      "error_api",
      "desconocida",
    ];
    for (const causa of causas) {
      expect(FRASES_CAUSA[causa]).toBeTruthy();
    }
    expect(Object.keys(FRASES_CAUSA).sort()).toEqual([...causas].sort());
  });
});
