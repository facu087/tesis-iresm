import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Unit tests for the frontend, following
// node_modules/next/dist/docs/01-app/02-guides/testing/vitest.md. The guide
// uses the vite-tsconfig-paths plugin for the `@/` alias; this Vite version
// resolves tsconfig paths natively, so `resolve.tsconfigPaths` replaces it.
export default defineConfig({
  plugins: [react()],
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
  },
});
