import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import axe from "axe-core";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { expect } from "vitest";
import { AuthProvider } from "../contexts/AuthContext";
import type { AuthUser, UserRole } from "../types/api";

/** Retries are disabled: a test asserting an error state should not wait for
 *  three silent retries first, and a flaky-looking timeout is worse than a
 *  clear failure. */
export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

type ProviderOptions = RenderOptions & {
  route?: string;
  queryClient?: QueryClient;
};

export function renderWithProviders(ui: ReactElement, options: ProviderOptions = {}) {
  const { route = "/", queryClient = makeQueryClient(), ...renderOptions } = options;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

export function renderWithAuth(ui: ReactElement, options: ProviderOptions = {}) {
  const { route = "/", queryClient = makeQueryClient(), ...renderOptions } = options;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

export function makeUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    email: "operator@technova.io",
    full_name: "Test Operator",
    role: "admin" as UserRole,
    is_active: true,
    organization_id: "22222222-2222-2222-2222-222222222222",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  } as AuthUser;
}

/** A `fetch` Response stand-in. Real Response is available in jsdom but
 *  constructing one for every case is noisier than this.
 *
 *  Status is a plain number rather than an options object on purpose: an
 *  options object reads fine at the call site but silently degrades to 200
 *  if someone passes `401` directly, which turns a test for an error path
 *  into a test for the happy path that still passes. */
export function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

export function emptyResponse(status = 204) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: async () => {
      throw new Error("no body");
    },
    text: async () => "",
  } as unknown as Response;
}

/**
 * Automated accessibility check. It catches a real and common class of bug —
 * unlabelled controls, bad contrast tokens, broken heading order — but it is
 * a floor, not a ceiling: axe cannot tell whether a flow makes sense to
 * someone using a screen reader. Treat a pass as "no known machine-detectable
 * violation", nothing more.
 */
export async function expectNoAxeViolations(container: HTMLElement) {
  const results = await axe.run(container, {
    rules: {
      // jsdom renders no real stylesheet, so computed colour is meaningless
      // here. Contrast is verified against the design tokens instead.
      "color-contrast": { enabled: false },
      // The test harness mounts fragments, not whole documents.
      region: { enabled: false },
    },
  });

  const summary = results.violations
    .map((violation) => `${violation.id}: ${violation.help} (${violation.nodes.length} node(s))`)
    .join("\n");

  expect(results.violations, summary).toHaveLength(0);
}
