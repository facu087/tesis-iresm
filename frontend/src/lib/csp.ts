/**
 * Content-Security-Policy of the frontend (Sprint 5, pending item of card #57).
 *
 * Next injects inline scripts to hydrate, so a strict policy needs a nonce
 * that changes on every request: `src/proxy.ts` generates it and Next adds it
 * to its own scripts by reading this header from the request
 * (node_modules/next/dist/docs/01-app/02-guides/content-security-policy.md).
 *
 * This module only builds the header value, so the policy can be tested
 * without a server.
 */

/** Backend origin used when NEXT_PUBLIC_API_URL is missing or invalid (same as lib/api.ts). */
export const DEFAULT_API_ORIGIN = "http://localhost:8000";

/** Request header that carries the nonce to Server Components (`app/layout.tsx`). */
export const NONCE_HEADER = "x-nonce";

export interface CspOptions {
  /** Base64 nonce of this request. */
  nonce: string;
  /** `next dev`: React needs `eval` for its error stacks and the dev server injects inline styles. */
  isDev: boolean;
  /** Backend base URL (NEXT_PUBLIC_API_URL); only its origin goes into `connect-src`. */
  apiUrl?: string;
}

/**
 * Origin of the backend that `lib/api.ts` calls with `fetch`.
 *
 * The backend lives on another origin, so `connect-src 'self'` alone would
 * block every API call. An unparsable value or one that is not http(s) falls
 * back to the default instead of producing a broken policy.
 */
export function apiOrigin(apiUrl: string | undefined): string {
  if (!apiUrl) return DEFAULT_API_ORIGIN;
  try {
    const url = new URL(apiUrl);
    if (url.protocol !== "http:" && url.protocol !== "https:") return DEFAULT_API_ORIGIN;
    return url.origin;
  } catch {
    return DEFAULT_API_ORIGIN;
  }
}

/** Generates a fresh nonce: 128 random bits, base64. */
export function generateNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

/**
 * Builds the header value.
 *
 * - Scripts: only those carrying this request's nonce (`'strict-dynamic'`
 *   lets them load the chunks they need). In development, `'unsafe-eval'` too.
 * - Styles: `<style>` and stylesheets need the nonce or our own origin. The
 *   `style` attribute (components set positions and animation delays with it)
 *   is allowed separately with `style-src-attr`: an attribute cannot run code.
 *   In development, inline `<style>` elements are allowed because the dev
 *   server injects them.
 * - `upgrade-insecure-requests` only in production with an https backend:
 *   with an http backend (development, or a production build served on a
 *   local network) it would rewrite the API calls to https and break them.
 */
export function buildCsp({ nonce, isDev, apiUrl }: CspOptions): string {
  const backend = apiOrigin(apiUrl);
  const upgrade = !isDev && backend.startsWith("https:");
  const directives = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' ${isDev ? "'unsafe-inline'" : `'nonce-${nonce}'`}`,
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    `connect-src 'self' ${backend}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(upgrade ? ["upgrade-insecure-requests"] : []),
  ];
  return directives.join("; ");
}
