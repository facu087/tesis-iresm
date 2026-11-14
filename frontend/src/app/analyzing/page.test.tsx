import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { analyzeWithProgress, type AnalysisProgress } from "@/lib/api";
import { inputStore } from "@/lib/inputStore";
import { reportStore } from "@/lib/reportStore";
import { makeReport } from "@/test/fixtures";
import type { StructuredReport } from "@/lib/types";
import AnalyzingPage from "./page";

// A stable router object: the page's effect depends on it, so a new object
// per render would restart the analysis.
const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/lib/api", () => ({
  analyzeWithProgress: vi.fn(),
  downloadPdf: vi.fn(),
}));

/** A running analysis the test drives: progress events, then the outcome. */
function runningAnalysis() {
  let emit!: (event: AnalysisProgress) => void;
  let resolve!: (report: StructuredReport) => void;
  let reject!: (error: unknown) => void;
  vi.mocked(analyzeWithProgress).mockImplementation((_input, onProgress) => {
    emit = onProgress;
    return new Promise<StructuredReport>((res, rej) => {
      resolve = res;
      reject = rej;
    });
  });
  return {
    emit: (event: AnalysisProgress) => act(async () => emit(event)),
    resolve: (report: StructuredReport) => act(async () => resolve(report)),
    reject: (error: unknown) => act(async () => reject(error)),
  };
}

describe("AnalyzingPage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    sessionStorage.clear();
    inputStore.set({ mode: "text", text: "Test clinical case" });
  });

  afterEach(() => {
    vi.useRealTimers();
    inputStore.clear();
  });

  it("sends the stored case and shows no step as started before the server says so", async () => {
    runningAnalysis();

    render(<AnalyzingPage />);

    expect(analyzeWithProgress).toHaveBeenCalledTimes(1);
    expect(vi.mocked(analyzeWithProgress).mock.calls[0][0]).toEqual({
      mode: "text",
      text: "Test clinical case",
    });
    expect(screen.getByRole("status")).toHaveTextContent("Iniciando…");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");

    // No timer moves the steps: only the server does.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });
    expect(screen.getByRole("status")).toHaveTextContent("Iniciando…");
    expect(router.push).not.toHaveBeenCalled();
  });

  it("follows the steps the server reports", async () => {
    const analysis = runningAnalysis();
    render(<AnalyzingPage />);

    await analysis.emit({ evento: "paso", paso: "01" });
    expect(screen.getByRole("status")).toHaveTextContent("Paso 1 de 8");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");

    await analysis.emit({ evento: "paso", paso: "04" });
    expect(screen.getByRole("status")).toHaveTextContent("Paso 4 de 8");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "3");
    expect(screen.getByText("Ronda 1 — Análisis paralelo").closest("li")).toHaveAttribute(
      "aria-current",
      "step",
    );
  });

  it("names the debate round the server reports", async () => {
    const analysis = runningAnalysis();
    render(<AnalyzingPage />);

    await analysis.emit({ evento: "paso", paso: "05" });
    expect(screen.queryByText(/Ronda \d de 4/)).not.toBeInTheDocument();

    await analysis.emit({ evento: "ronda", ronda: 3 });
    expect(screen.getByRole("status")).toHaveTextContent("Paso 5 de 8 — Ronda 3 de 4");

    // The round belongs to the debate: it is gone once the next step starts.
    await analysis.emit({ evento: "paso", paso: "06" });
    expect(screen.getByRole("status")).toHaveTextContent("Paso 6 de 8");
    expect(screen.queryByText(/Ronda 3 de 4/)).not.toBeInTheDocument();
  });

  it("never moves backwards and ignores a step it does not know", async () => {
    const analysis = runningAnalysis();
    render(<AnalyzingPage />);

    await analysis.emit({ evento: "paso", paso: "06" });
    await analysis.emit({ evento: "paso", paso: "02" });
    await analysis.emit({ evento: "paso", paso: "99" });

    expect(screen.getByRole("status")).toHaveTextContent("Paso 6 de 8");
  });

  it("saves the report and navigates as soon as it arrives", async () => {
    const analysis = runningAnalysis();
    render(<AnalyzingPage />);
    await analysis.emit({ evento: "paso", paso: "08" });
    expect(router.push).not.toHaveBeenCalled();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "7");

    const report = makeReport();
    await analysis.resolve(report);

    expect(router.push).toHaveBeenCalledTimes(1);
    expect(router.push).toHaveBeenCalledWith("/report");
    expect(reportStore.getSnapshot()).toEqual(report);
    expect(screen.getByRole("status")).toHaveTextContent("Completado — redirigiendo…");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "8");
    expect(inputStore.get()).toBeNull();
  });

  it("sends an uploaded file as it was stored", async () => {
    const file = new File(["%PDF"], "case.pdf", { type: "application/pdf" });
    inputStore.set({ mode: "file", file });
    runningAnalysis();

    render(<AnalyzingPage />);

    expect(vi.mocked(analyzeWithProgress).mock.calls[0][0]).toEqual({ mode: "file", file });
  });

  it("shows the backend error message and does not navigate", async () => {
    const analysis = runningAnalysis();
    render(<AnalyzingPage />);
    await analysis.emit({ evento: "paso", paso: "04" });

    await analysis.reject(new Error("msg from backend"));

    expect(screen.getByRole("heading", { name: "Error en el análisis" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("msg from backend");
    expect(router.push).not.toHaveBeenCalled();
  });

  it("replaces the browser's network error with a readable message", async () => {
    const analysis = runningAnalysis();
    render(<AnalyzingPage />);

    await analysis.reject(new TypeError("Failed to fetch"));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "No se pudo conectar con el servidor. Revisá tu conexión e intentá de nuevo.",
    );
    expect(screen.queryByText(/Failed to fetch/)).not.toBeInTheDocument();
    expect(router.push).not.toHaveBeenCalled();
  });

  it("sends the user back to the upload view when there is no case", async () => {
    inputStore.clear();

    render(<AnalyzingPage />);

    expect(router.replace).toHaveBeenCalledWith("/analizar");
    expect(analyzeWithProgress).not.toHaveBeenCalled();
    expect(router.push).not.toHaveBeenCalled();
  });
});
