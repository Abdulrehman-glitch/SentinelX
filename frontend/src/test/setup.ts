import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// jsdom has no fetch of its own worth using. Every test gets a fresh mock, so
// one test's queued responses can never leak into the next.
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  document.cookie = "";
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
