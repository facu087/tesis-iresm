import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: false,
  // Next 16 movió la opción a `turbopack` (top-level): `experimental.turbo`
  // ya no existe y rompía el chequeo de tipos de `next build`.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
