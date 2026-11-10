// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { proxy } from "@/proxy";

function nonceOf(csp: string | null): string | undefined {
  return csp?.match(/'nonce-([^']+)'/)?.[1];
}

describe("proxy", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("sends the policy to the browser and the same nonce to the renderer", () => {
    const response = proxy(new NextRequest("http://localhost:3000/report"));

    const csp = response.headers.get("Content-Security-Policy");
    const nonce = nonceOf(csp);
    expect(nonce).toBeTruthy();
    // NextResponse.next forwards the modified request headers with this prefix.
    expect(response.headers.get("x-middleware-request-x-nonce")).toBe(nonce);
    expect(response.headers.get("x-middleware-request-content-security-policy")).toBe(csp);
  });

  it("uses a new nonce on every request", () => {
    const first = proxy(new NextRequest("http://localhost:3000/"));
    const second = proxy(new NextRequest("http://localhost:3000/"));
    expect(nonceOf(first.headers.get("Content-Security-Policy"))).not.toBe(
      nonceOf(second.headers.get("Content-Security-Policy")),
    );
  });

  it("allows the backend configured in NEXT_PUBLIC_API_URL", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.nexus.example");
    const response = proxy(new NextRequest("http://localhost:3000/analizar"));
    expect(response.headers.get("Content-Security-Policy")).toContain(
      "connect-src 'self' https://api.nexus.example",
    );
  });
});
