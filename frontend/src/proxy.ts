import { NextResponse, type NextRequest } from "next/server";

import { buildCsp, generateNonce, NONCE_HEADER } from "@/lib/csp";

/**
 * Adds the Content-Security-Policy with a fresh nonce to every page.
 *
 * The policy goes on the request too: Next reads the nonce from it while
 * rendering and adds it to its own scripts. `app/layout.tsx` reads it from
 * `x-nonce` for the theme script. Pages become dynamically rendered, which
 * the nonce requires (see lib/csp.ts).
 */
export function proxy(request: NextRequest) {
  const nonce = generateNonce();
  const csp = buildCsp({
    nonce,
    isDev: process.env.NODE_ENV === "development",
    apiUrl: process.env.NEXT_PUBLIC_API_URL,
  });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(NONCE_HEADER, nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    // Every path except static files and the image optimizer, and not on
    // link prefetches: those responses carry no HTML that runs scripts.
    {
      source: "/((?!_next/static|_next/image|favicon.ico|icon.svg).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
