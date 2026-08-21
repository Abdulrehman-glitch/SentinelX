/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Deliberately separate from vite.config.ts rather than a `test` block inside
// it: the production build config should not carry test-only plugins or a
// jsdom environment, and keeping them apart makes it obvious that nothing
// here affects what ships.
//
// Tailwind is omitted on purpose. These tests assert behaviour and
// accessibility, never computed styles, so processing the stylesheet would
// only slow every run down.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
    // Results go to the console. No JSON/JUnit reporter and no coverage
    // bundle by default — CI must not persist artifacts
    // (docs/adr/0004-ci-artifact-policy.md).
    reporters: ["default"],
  },
});
