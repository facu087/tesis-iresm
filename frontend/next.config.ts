import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: false,
  experimental: {
    turbo: {
      root: __dirname,
    },
  },
};

export default nextConfig;
