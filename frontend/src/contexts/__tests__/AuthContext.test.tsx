import { QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "../AuthContext";
import { authStorage, CSRF_COOKIE_NAME } from "../../lib/authStorage";
import { setSessionEndedHandler } from "../../lib/api";
import { jsonResponse, makeQueryClient, makeUser } from "../../test/utils";

function fetchMock() {
  return globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
}

const USER = makeUser();

const SESSION_BODY = {
  access_token: "fresh-access-token",
  token_type: "bearer",
  expires_in: 900,
  user: USER,
};

/** Minimal consumer that renders the pieces of the context under test. */
function AuthProbe() {
  const { user, isLoading, isAuthenticated, errorMessage, login, logout, hasMinRole } = useAuth();

  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <span data-testid="email">{user?.email ?? "none"}</span>
      <span data-testid="error">{errorMessage ?? "none"}</span>
      <span data-testid="min-engineer">{String(hasMinRole("engineer"))}</span>
      <button onClick={() => login({ email: "a@b.c", password: "pw" }).catch(() => undefined)}>
        Sign in
      </button>
      <button onClick={() => logout()}>Sign out</button>
    </div>
  );
}

function renderProbe() {
  const queryClient = makeQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>{children}</MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );
  }

  return render(<AuthProbe />, { wrapper: Wrapper });
}

beforeEach(() => {
  authStorage.clearToken();
  setSessionEndedHandler(null);
  document.cookie = `${CSRF_COOKIE_NAME}=csrf-token`;
});

describe("cold start", () => {
  it("restores a session from the refresh cookie without any stored token", async () => {
    // The access token is never persisted, so a page reload legitimately
    // starts with nothing in memory. The cookie is what survives.
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(SESSION_BODY)) // /auth/refresh
      .mockResolvedValueOnce(jsonResponse(USER)); // /auth/me

    renderProbe();

    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    expect(screen.getByTestId("email")).toHaveTextContent(USER.email);
    expect(authStorage.getToken()).toBe("fresh-access-token");
  });

  it("settles as signed out when there is no live session", async () => {
    fetchMock().mockResolvedValue(jsonResponse({ detail: "No active session." }, 401));

    renderProbe();

    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    expect(screen.getByTestId("email")).toHaveTextContent("none");
  });

  it("shows a loading state before the session is resolved", async () => {
    let release: (value: Response) => void = () => {};
    fetchMock().mockImplementationOnce(
      () => new Promise<Response>((resolve) => (release = resolve)),
    );

    renderProbe();

    expect(screen.getByTestId("loading")).toHaveTextContent("true");

    await act(async () => {
      release(jsonResponse({ detail: "no session" }, 401));
    });
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
  });

  it("does not leave the user signed in when the backend is unreachable", async () => {
    fetchMock().mockRejectedValue(new TypeError("Failed to fetch"));

    renderProbe();

    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
  });
});

describe("sign in", () => {
  it("stores the token with its lifetime and exposes the user", async () => {
    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "no session" }, 401));
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));

    fetchMock().mockResolvedValueOnce(jsonResponse(SESSION_BODY));
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    expect(authStorage.getToken()).toBe("fresh-access-token");
    expect(authStorage.msUntilExpiry()).toBeGreaterThan(0);
  });

  it("surfaces a rejected sign-in as an error message and stays signed out", async () => {
    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "no session" }, 401));
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));

    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "Invalid email or password." }, 401));
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(screen.getByTestId("error")).toHaveTextContent("Invalid email or password."),
    );
    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
  });

  it("surfaces a rate-limited sign-in rather than failing silently", async () => {
    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "no session" }, 401));
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));

    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "" }, 429));
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(screen.getByTestId("error")).toHaveTextContent(/too many requests/i),
    );
  });
});

describe("sign out", () => {
  it("clears the token and the user", async () => {
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(SESSION_BODY))
      .mockResolvedValueOnce(jsonResponse(USER));
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));

    fetchMock().mockResolvedValueOnce(jsonResponse({ message: "Signed out." }));
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("false"));
    expect(authStorage.getToken()).toBeNull();
  });

  it("still signs the user out locally when the logout call fails", async () => {
    // Losing the network must not trap someone in a signed-in shell.
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(SESSION_BODY))
      .mockResolvedValueOnce(jsonResponse(USER));
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));

    fetchMock().mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("false"));
    expect(authStorage.getToken()).toBeNull();
  });
});

describe("session ended elsewhere", () => {
  it("drops to signed out with an explanation when the API reports the session gone", async () => {
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(SESSION_BODY))
      .mockResolvedValueOnce(jsonResponse(USER));
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));

    // Drives the real api layer so the session-ended callback fires the way it
    // would after a revoked session, a logout-all elsewhere, or replay
    // detection — not by poking state directly.
    const { sentinelxApi } = await import("../../lib/api");
    fetchMock().mockResolvedValue(jsonResponse({ detail: "Session is no longer valid." }, 401));

    await act(async () => {
      await sentinelxApi.getUsers().catch(() => undefined);
    });

    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("false"));
    expect(screen.getByTestId("error")).toHaveTextContent(/session ended/i);
  });
});

describe("role helpers", () => {
  it("compares against the role hierarchy, not an exact match", async () => {
    const admin = makeUser({ role: "admin" });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse({ ...SESSION_BODY, user: admin }))
      .mockResolvedValueOnce(jsonResponse(admin));
    renderProbe();

    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    // admin (60) outranks engineer (40).
    expect(screen.getByTestId("min-engineer")).toHaveTextContent("true");
  });

  it("refuses a lower role", async () => {
    const viewer = makeUser({ role: "viewer" });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse({ ...SESSION_BODY, user: viewer }))
      .mockResolvedValueOnce(jsonResponse(viewer));
    renderProbe();

    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    expect(screen.getByTestId("min-engineer")).toHaveTextContent("false");
  });

  it("refuses everything when nobody is signed in", async () => {
    fetchMock().mockResolvedValue(jsonResponse({ detail: "no session" }, 401));
    renderProbe();

    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
    expect(screen.getByTestId("min-engineer")).toHaveTextContent("false");
  });
});
