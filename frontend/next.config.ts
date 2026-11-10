import type { NextConfig } from "next";

// Encabezados de seguridad de toda respuesta del frontend (tarjeta #57).
// La Content-Security-Policy no va acá: necesita un nonce distinto en cada
// pedido, así que la agrega `src/proxy.ts` (política en `src/lib/csp.ts`).
const encabezadosDeSeguridad = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=()",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  // Solo en producción: en desarrollo se sirve por http y el navegador lo ignora.
  ...(process.env.NODE_ENV === "production"
    ? [
        {
          key: "Strict-Transport-Security",
          value: "max-age=31536000; includeSubDomains",
        },
      ]
    : []),
];

const nextConfig: NextConfig = {
  reactStrictMode: false,
  // No anunciar el framework en cada respuesta.
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: encabezadosDeSeguridad }];
  },
  // Next 16 movió la opción a `turbopack` (top-level): `experimental.turbo`
  // ya no existe y rompía el chequeo de tipos de `next build`.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
