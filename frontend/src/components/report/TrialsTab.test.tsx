import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EnsayosTab } from "./TrialsTab";
import { makeReport } from "@/test/fixtures";
import type { StructuredReport, TrialSearchSummary } from "@/lib/types";

function reportWithSearch(overrides: Partial<TrialSearchSummary>): StructuredReport {
  return {
    ...makeReport(),
    trial_search: {
      estado_clinicaltrials: "ok",
      estado_orphanet: "ok",
      planificacion: "ok",
      evaluacion: "ok",
      terminos_consultados: ["hereditary ATTR amyloidosis"],
      encontrados: 3,
      excluidos_por_edad: 0,
      excluidos_por_sexo: 0,
      evaluaciones_descartadas: 0,
      ...overrides,
    },
  };
}

describe("EnsayosTab — trials excluded by age and sex", () => {
  it("says how many trials are not shown and why", () => {
    render(<EnsayosTab report={reportWithSearch({ excluidos_por_edad: 2, excluidos_por_sexo: 1 })} />);
    expect(screen.getByText(/No se muestran 3 ensayos/)).toBeInTheDocument();
    expect(screen.getByText(/2 por edad y 1 por sexo/)).toBeInTheDocument();
  });

  it("uses the singular and names only the filter that excluded", () => {
    render(<EnsayosTab report={reportWithSearch({ excluidos_por_edad: 1 })} />);
    expect(screen.getByText(/No se muestra 1 ensayo/)).toBeInTheDocument();
    expect(screen.queryByText(/por sexo/)).not.toBeInTheDocument();
  });

  it("says nothing when no trial was excluded", () => {
    render(<EnsayosTab report={reportWithSearch({})} />);
    expect(screen.queryByText(/No se muestra/)).not.toBeInTheDocument();
  });

  it("says nothing on a report saved before the trial navigator", () => {
    render(<EnsayosTab report={makeReport()} />);
    expect(screen.queryByText(/No se muestra/)).not.toBeInTheDocument();
  });
});
