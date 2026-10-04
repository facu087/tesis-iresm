/**
 * Cliente de API — conecta el frontend con el backend FastAPI de NEXUS.
 * Base URL configurada via NEXT_PUBLIC_API_URL (ver .env.local).
 */

import type {
  ApiError,
  CuentaEstado,
  CuentaPendiente,
  RegistroMedicoPayload,
  StructuredReport,
} from "./types";

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

/** POST/JSON genérico contra el backend, con la cookie de sesión incluida. */
async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const error: ApiError = await res.json().catch(() => ({
      detail: res.statusText,
    }));
    throw new Error(extractErrorMessage(error));
  }
  return res.json() as Promise<T>;
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
    credentials: "include",
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
    credentials: "include",
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
    credentials: "include",
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

/* ── Cuentas de médico (Sprint 4 — registro-medicos-matricula) ──────────── */

/** Alta de médico. La cuenta nace `pendiente`. */
export async function registrarMedico(payload: RegistroMedicoPayload): Promise<CuentaEstado> {
  return postJson<CuentaEstado>("/api/registro", payload);
}

/** Corrección y reenvío tras un rechazo: vuelve la cuenta a `pendiente`. */
export async function reenviarRegistro(payload: RegistroMedicoPayload): Promise<CuentaEstado> {
  const res = await fetch(`${API_BASE}/api/registro`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error: ApiError = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(extractErrorMessage(error));
  }
  return res.json() as Promise<CuentaEstado>;
}

/** Login con email institucional y contraseña. Deja la cookie de sesión fijada. */
export async function login(email: string, password: string): Promise<CuentaEstado> {
  return postJson<CuentaEstado>("/api/login", { email, password });
}

/** Cierra la sesión activa (invalida la cookie del lado del servidor). */
export async function logout(): Promise<void> {
  await postJson<{ ok: boolean }>("/api/logout", {});
}

/**
 * Estado de la cuenta propia. Devuelve `null` si no hay sesión activa (401)
 * en vez de lanzar, para que la vista pueda redirigir sin un try/catch extra.
 */
export async function obtenerCuenta(): Promise<CuentaEstado | null> {
  const res = await fetch(`${API_BASE}/api/cuenta`, { credentials: "include" });
  if (res.status === 401) return null;
  if (!res.ok) {
    throw new Error("No se pudo consultar el estado de la cuenta.");
  }
  return res.json() as Promise<CuentaEstado>;
}

/* ── Revisión admin (Sprint 4 — revision-admin-matriculas) ───────────────── */

/** Lista las cuentas de médico en estado `pendiente`. Requiere sesión admin. */
export async function listarPendientes(): Promise<CuentaPendiente[]> {
  const res = await fetch(`${API_BASE}/api/admin/pendientes`, { credentials: "include" });
  if (!res.ok) {
    throw new Error("No se pudo obtener el listado de cuentas pendientes.");
  }
  return res.json() as Promise<CuentaPendiente[]>;
}

/** Aprueba una cuenta pendiente. `fuente_consultada` es obligatoria. */
export async function aprobarCuenta(
  cuentaId: number,
  fuenteConsultada: string,
  nota: string = ""
): Promise<CuentaEstado> {
  return postJson<CuentaEstado>(`/api/admin/cuentas/${cuentaId}/aprobar`, {
    fuente_consultada: fuenteConsultada,
    nota,
  });
}

/** Rechaza una cuenta pendiente. `motivo` es obligatorio y queda visible para el médico. */
export async function rechazarCuenta(cuentaId: number, motivo: string): Promise<CuentaEstado> {
  return postJson<CuentaEstado>(`/api/admin/cuentas/${cuentaId}/rechazar`, { motivo });
}
