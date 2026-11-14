import { afterEach, describe, expect, it, vi } from "vitest";
import { analyzeWithProgress, type AnalysisProgress } from "./api";
import { makeReport } from "@/test/fixtures";

/** A streamed NDJSON response, split into the given network chunks. */
function streamed(chunks: string[], init: ResponseInit = { status: 200 }): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, init);
}

function line(event: unknown): string {
  return JSON.stringify(event) + "\n";
}

describe("analyzeWithProgress", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the text to the streaming endpoint with the session cookie", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(streamed([line({ evento: "reporte", reporte: makeReport() })]));
    vi.stubGlobal("fetch", fetchMock);

    await analyzeWithProgress({ mode: "text", text: "Test clinical case" }, () => {});

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/analyze\/stream$/);
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect((init.body as FormData).get("text")).toBe("Test clinical case");
  });

  it("posts an uploaded file in the file field", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(streamed([line({ evento: "reporte", reporte: makeReport() })]));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["%PDF"], "case.pdf", { type: "application/pdf" });

    await analyzeWithProgress({ mode: "file", file }, () => {});

    const body = fetchMock.mock.calls[0][1].body as FormData;
    expect((body.get("file") as File).name).toBe("case.pdf");
    expect(body.get("text")).toBeNull();
  });

  it("reports each progress event in order and resolves with the report", async () => {
    const report = makeReport();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        streamed([
          line({ evento: "paso", paso: "01" }),
          line({ evento: "paso", paso: "05" }) + line({ evento: "ronda", ronda: 2 }),
          line({ evento: "reporte", reporte: report }),
        ]),
      ),
    );
    const seen: AnalysisProgress[] = [];

    const result = await analyzeWithProgress({ mode: "text", text: "x" }, (e) => seen.push(e));

    expect(seen).toEqual([
      { evento: "paso", paso: "01" },
      { evento: "paso", paso: "05" },
      { evento: "ronda", ronda: 2 },
    ]);
    expect(result).toEqual(report);
  });

  it("joins an event that arrives split across two network chunks", async () => {
    const report = makeReport();
    const whole = line({ evento: "paso", paso: "03" }) + line({ evento: "reporte", reporte: report });
    const cut = 12;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(streamed([whole.slice(0, cut), whole.slice(cut)])),
    );
    const seen: AnalysisProgress[] = [];

    const result = await analyzeWithProgress({ mode: "text", text: "x" }, (e) => seen.push(e));

    expect(seen).toEqual([{ evento: "paso", paso: "03" }]);
    expect(result).toEqual(report);
  });

  it("accepts a final event without a trailing newline", async () => {
    const report = makeReport();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(streamed([JSON.stringify({ evento: "reporte", reporte: report })])),
    );

    await expect(analyzeWithProgress({ mode: "text", text: "x" }, () => {})).resolves.toEqual(report);
  });

  it("rejects with the detail of an error event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        streamed([
          line({ evento: "paso", paso: "01" }),
          line({ evento: "error", status: 415, detail: "Formato no soportado." }),
        ]),
      ),
    );

    await expect(analyzeWithProgress({ mode: "text", text: "x" }, () => {})).rejects.toThrow(
      "Formato no soportado.",
    );
  });

  it("rejects with the backend detail when the request is refused before streaming", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "El archivo supera el límite de 50 MB." }), {
          status: 413,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(analyzeWithProgress({ mode: "text", text: "x" }, () => {})).rejects.toThrow(
      "El archivo supera el límite de 50 MB.",
    );
  });

  it("rejects with a readable message when the stream ends without a report", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(streamed([line({ evento: "paso", paso: "04" })])),
    );

    await expect(analyzeWithProgress({ mode: "text", text: "x" }, () => {})).rejects.toThrow(
      "La conexión se cortó antes de que terminara el análisis. Intentá de nuevo.",
    );
  });

  it("ignores an event of a kind it does not know", async () => {
    const report = makeReport();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        streamed([line({ evento: "futuro", dato: 1 }), line({ evento: "reporte", reporte: report })]),
      ),
    );
    const seen: AnalysisProgress[] = [];

    await expect(
      analyzeWithProgress({ mode: "text", text: "x" }, (e) => seen.push(e)),
    ).resolves.toEqual(report);
    expect(seen).toEqual([]);
  });
});
