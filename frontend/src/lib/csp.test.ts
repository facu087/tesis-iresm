import { describe, expect, it } from "vitest";

import { apiOrigin, buildCsp, DEFAULT_API_ORIGIN, generateNonce } from "@/lib/csp";

/** Parses a header value into directive → sources. */
function directives(csp: string): Map<string, string[]> {
  return new Map(
    csp.split(";").map((part) => {
      const [name, ...sources] = part.trim().split(/\s+/);
      return [name, sources];
    }),
  );
}

describe("buildCsp in production", () => {
  const csp = directives(
    buildCsp({ nonce: "abc123", isDev: false, apiUrl: "https://api.nexus.example/v1" }),
  );

  it("only runs scripts that carry the request nonce", () => {
    expect(csp.get("script-src")).toEqual(["'self'", "'nonce-abc123'", "'strict-dynamic'"]);
  });

  it("never allows eval or inline scripts without the nonce", () => {
    const scripts = csp.get("script-src") ?? [];
    expect(scripts).not.toContain("'unsafe-eval'");
    expect(scripts).not.toContain("'unsafe-inline'");
  });

  it("requires the nonce for style elements and allows style attributes", () => {
    expect(csp.get("style-src")).toEqual(["'self'", "'nonce-abc123'"]);
    expect(csp.get("style-src-attr")).toEqual(["'unsafe-inline'"]);
  });

  it("lets the page call the backend origin and nothing else", () => {
    expect(csp.get("connect-src")).toEqual(["'self'", "https://api.nexus.example"]);
  });

  it("blocks framing, plugins, base and form hijacking, and upgrades http", () => {
    expect(csp.get("frame-ancestors")).toEqual(["'none'"]);
    expect(csp.get("object-src")).toEqual(["'none'"]);
    expect(csp.get("base-uri")).toEqual(["'self'"]);
    expect(csp.get("form-action")).toEqual(["'self'"]);
    expect(csp.has("upgrade-insecure-requests")).toBe(true);
  });
});

describe("buildCsp in development", () => {
  const csp = directives(buildCsp({ nonce: "abc123", isDev: true }));

  it("allows eval for React's dev error stacks, still with the nonce", () => {
    expect(csp.get("script-src")).toEqual([
      "'self'",
      "'nonce-abc123'",
      "'strict-dynamic'",
      "'unsafe-eval'",
    ]);
  });

  it("allows the inline styles the dev server injects", () => {
    expect(csp.get("style-src")).toEqual(["'self'", "'unsafe-inline'"]);
  });

  it("does not upgrade the plain-http local backend", () => {
    expect(csp.has("upgrade-insecure-requests")).toBe(false);
  });
});

describe("buildCsp in production with an http backend", () => {
  it("does not upgrade requests, which would break the API calls", () => {
    const csp = directives(
      buildCsp({ nonce: "abc123", isDev: false, apiUrl: "http://192.168.0.10:8000" }),
    );
    expect(csp.has("upgrade-insecure-requests")).toBe(false);
    expect(csp.get("connect-src")).toEqual(["'self'", "http://192.168.0.10:8000"]);
  });
});

describe("apiOrigin", () => {
  it("keeps only the origin of the backend URL", () => {
    expect(apiOrigin("http://localhost:8000/api")).toBe("http://localhost:8000");
  });

  it.each([undefined, "", "not a url", "ftp://files.example", "javascript:alert(1)"])(
    "falls back to the default backend for %j",
    (value) => {
      expect(apiOrigin(value)).toBe(DEFAULT_API_ORIGIN);
    },
  );
});

describe("generateNonce", () => {
  it("returns 128 random bits in base64, different each time", () => {
    const first = generateNonce();
    expect(atob(first)).toHaveLength(16);
    expect(generateNonce()).not.toBe(first);
  });
});
