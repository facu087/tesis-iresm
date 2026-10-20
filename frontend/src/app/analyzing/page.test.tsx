import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { analyzeFile, analyzeText } from "@/lib/api";
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
  analyzeFile: vi.fn(),
  analyzeText: vi.fn(),
  downloadPdf: vi.fn(),
}));

/** Simulated duration of the eight steps, as paced by the page (ms). */
const STEP_MS = [1500, 1000, 4000, 8000, 12000, 9000, 5000, 1500];
const ANIMATION_MS = STEP_MS.reduce((a, b) => a + b, 0);
const CATCH_UP_MS = 350;

/** Advances fake time and flushes the promises and renders it triggers. */
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
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

  it("waits for the steps to catch up when the report arrives early", async () => {
    const report = makeReport();
    vi.mocked(analyzeText).mockResolvedValue(report);

    render(<AnalyzingPage />);
    expect(analyzeText).toHaveBeenCalledWith("Test clinical case");

    // The first step keeps its pace even though the report is already back.
    await advance(STEP_MS[0] - 1);
    expect(router.push).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("Paso 1 de 8");

    // Then the remaining seven steps catch up, one every CATCH_UP_MS.
    await advance(1 + 6 * CATCH_UP_MS);
    expect(router.push).not.toHaveBeenCalled();

    await advance(CATCH_UP_MS);
    expect(router.push).toHaveBeenCalledTimes(1);
    expect(router.push).toHaveBeenCalledWith("/report");
    expect(reportStore.getSnapshot()).toEqual(report);
    expect(screen.getByRole("status")).toHaveTextContent("Completado — redirigiendo…");
    expect(inputStore.get()).toBeNull();
  });

  it("navigates right after the response when the animation already ended", async () => {
    const pending = deferred<StructuredReport>();
    vi.mocked(analyzeText).mockReturnValue(pending.promise);

    render(<AnalyzingPage />);

    // The last step stays in progress while the request is still running.
    await advance(ANIMATION_MS + 10_000);
    expect(router.push).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("Paso 8 de 8");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "7");

    const report = makeReport();
    await act(async () => {
      pending.resolve(report);
    });

    expect(router.push).toHaveBeenCalledTimes(1);
    expect(router.push).toHaveBeenCalledWith("/report");
    expect(reportStore.getSnapshot()).toEqual(report);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "8");
  });

  it("uses analyzeFile for an uploaded file", async () => {
    const file = new File(["%PDF"], "case.pdf", { type: "application/pdf" });
    inputStore.set({ mode: "file", file });
    vi.mocked(analyzeFile).mockResolvedValue(makeReport());

    render(<AnalyzingPage />);
    await advance(ANIMATION_MS);

    expect(analyzeFile).toHaveBeenCalledWith(file);
    expect(analyzeText).not.toHaveBeenCalled();
    expect(router.push).toHaveBeenCalledWith("/report");
  });

  it("shows the backend error message and does not navigate", async () => {
    vi.mocked(analyzeText).mockRejectedValue(new Error("msg from backend"));

    render(<AnalyzingPage />);
    await advance(0);

    expect(screen.getByRole("heading", { name: "Error en el análisis" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("msg from backend");

    // The pacing timers left behind must not navigate either.
    await advance(ANIMATION_MS + 10_000);
    expect(router.push).not.toHaveBeenCalled();
  });

  it("replaces the browser's network error with a readable message", async () => {
    vi.mocked(analyzeText).mockRejectedValue(new TypeError("Failed to fetch"));

    render(<AnalyzingPage />);
    await advance(0);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "No se pudo conectar con el servidor. Revisá tu conexión e intentá de nuevo.",
    );
    expect(screen.queryByText(/Failed to fetch/)).not.toBeInTheDocument();
    expect(router.push).not.toHaveBeenCalled();
  });

  it("sends the user back to the upload view when there is no case", async () => {
    inputStore.clear();

    render(<AnalyzingPage />);
    await advance(ANIMATION_MS);

    expect(router.replace).toHaveBeenCalledWith("/analizar");
    expect(analyzeText).not.toHaveBeenCalled();
    expect(analyzeFile).not.toHaveBeenCalled();
    expect(router.push).not.toHaveBeenCalled();
  });
});
