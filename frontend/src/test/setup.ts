import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Globals are off, so RTL cannot register its own cleanup: unmount here.
afterEach(() => {
  cleanup();
});
