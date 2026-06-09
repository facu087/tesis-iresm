/**
 * Cliente de API — conecta el frontend con el backend FastAPI de NEXUS.
 * Base URL configurada via NEXT_PUBLIC_API_URL (ver .env.local).
 */

import type { ApiError, StructuredReport } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Extrae un mensaje legible de un error de la API. */
function extractErrorMessage(error: ApiError): string {
  if (typeof error.detail === "string") return error.detail;
  if (Array.isArray(error.detail) && error.detail.length > 0) {
    return error.detail.map((e) => e.msg).join(", ");
  }
  return "Error desconocido del servidor.";
}

/**
 * Analiza un caso clínico enviado como texto plano.
 * Ejecuta el pipeline completo en el backend y devuelve el reporte estructurado.
 */
export async function analyzeText(text: string): Promise<StructuredReport> {
  const form = new FormData();
  form.append("text", text);

  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const error: ApiError = await res.json().catch(() => ({
      detail: res.statusText,
    }));
    throw new Error(extractErrorMessage(error));
  }

  return res.json() as Promise<StructuredReport>;
}

/**
 * Analiza un caso clínico enviado como archivo PDF.
 * El backend extrae el texto (nativo u OCR) antes de ejecutar el pipeline.
 */
export async function analyzeFile(file: File): Promise<StructuredReport> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const error: ApiError = await res.json().catch(() => ({
      detail: res.statusText,
    }));
    throw new Error(extractErrorMessage(error));
  }

  return res.json() as Promise<StructuredReport>;
}

/**
 * Descarga el reporte como archivo PDF.
 * Recibe el StructuredReport ya generado y devuelve un Blob listo para descargar.
 */
export async function downloadPdf(report: StructuredReport): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/report/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(report),
  });

  if (!res.ok) {
    throw new Error("Error al generar el PDF. Intentá de nuevo.");
  }

  return res.blob();
}

/**
 * Verifica que el backend esté disponible.
 * Útil para mostrar un indicador de estado al usuario.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      signal: AbortSignal.timeout(3000),
    });
    return res.ok;
  } catch {
    return false;
  }
}
