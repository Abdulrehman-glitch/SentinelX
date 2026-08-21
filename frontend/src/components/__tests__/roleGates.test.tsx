import { QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PermissionGate } from "../PermissionGate";
import { ProtectedRoute } from "../ProtectedRoute";
import { AuthProvider } from "../../contexts/AuthContext";
import { authStorage, CSRF_COOKIE_NAME } from "../../lib/authStorage";
import { setSessionEndedHandler } from "../../lib/api";
import { jsonResponse, makeQueryClient, makeUser } from "../../test/utils";
import type { UserRole } from "../../types/api";

function fetchMock() {
  return globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
}

function signedInAs(role: UserRole) {
  const user = makeUser({ role });
  fetchMock()
    .mockResolvedValueOnce(
      jsonResponse({ access_token: "t", token_type: "bearer", expires_in: 900, user }),
    )
    .mockResolvedValueOnce(jsonResponse(user));
}

function signedOut() {
  fetchMock().mockResolvedValue(jsonResponse({ detail: "No active session." }, 401));
}

function renderRoutes(node: ReactNode, route = "/console") {
  const queryClient = makeQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[route]}>{node}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  authStorage.clearToken();
  setSessionEndedHandler(null);
  document.cookie = `${CSRF_COOKIE_NAME}=csrf-token`;
});

describe("ProtectedRoute", () => {
  const tree = (
    <Routes>
      <Route path="/login" element={<div>Login screen</div>} />
      <Route path="/" element={<div>Landing</div>} />
      <Route element={<ProtectedRoute allowedRoles={["admin", "owner", "platform_admin"]} />}>
        <Route path="/console" element={<div>Admin console</div>} />
      </Route>
    </Routes>
  );

  it("holds the route while the session is still resolving", async () => {
    // Resolved before the test ends rather than left dangling: the api
    // layer's single-flight refresh keeps one module-level promise, so a
    // never-settling fetch would park it and hang every later test.
    let release: (value: Response) => void = () => {};
    fetchMock().mockImplementationOnce(
      () => new Promise<Response>((resolve) => (release = resolve)),
    );

    renderRoutes(tree);

    // Rendering the guarded page first and redirecting after would flash
    // privileged content to someone who may not be allowed to see it.
    expect(screen.getByText(/loading secure session/i)).toBeInTheDocument();
    expect(screen.queryByText("Admin console")).not.toBeInTheDocument();

    await act(async () => {
      release(jsonResponse({ detail: "No active session." }, 401));
    });
    await waitFor(() => expect(screen.getByText("Login screen")).toBeInTheDocument());
  });

  it("sends an anonymous visitor to the login screen", async () => {
    signedOut();
    renderRoutes(tree);

    await waitFor(() => expect(screen.getByText("Login screen")).toBeInTheDocument());
    expect(screen.queryByText("Admin console")).not.toBeInTheDocument();
  });

  it("admits a user whose role is allowed", async () => {
    signedInAs("admin");
    renderRoutes(tree);

    await waitFor(() => expect(screen.getByText("Admin console")).toBeInTheDocument());
  });

  it("turns away an authenticated user whose role is not allowed", async () => {
    // The server enforces this too; this stops the UI from rendering a page
    // that would only produce 403s.
    signedInAs("viewer");
    renderRoutes(tree);

    await waitFor(() => expect(screen.getByText("Landing")).toBeInTheDocument());
    expect(screen.queryByText("Admin console")).not.toBeInTheDocument();
  });

  it("admits any authenticated role when no allowlist is given", async () => {
    signedInAs("viewer");
    renderRoutes(
      <Routes>
        <Route path="/login" element={<div>Login screen</div>} />
        <Route element={<ProtectedRoute />}>
          <Route path="/console" element={<div>Shared page</div>} />
        </Route>
      </Routes>,
    );

    await waitFor(() => expect(screen.getByText("Shared page")).toBeInTheDocument());
  });
});

describe("PermissionGate", () => {
  const tree = (
    <PermissionGate roles={["admin", "owner"]} fallback={<span>Not available</span>}>
      <button>Approve recovery command</button>
    </PermissionGate>
  );

  it("shows the control to a permitted role", async () => {
    signedInAs("admin");
    renderRoutes(tree);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /approve recovery command/i })).toBeInTheDocument(),
    );
  });

  it("hides the control from a role without permission", async () => {
    signedInAs("engineer");
    renderRoutes(tree);

    await waitFor(() => expect(screen.getByText("Not available")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
  });

  it("hides the control from an anonymous visitor", async () => {
    signedOut();
    renderRoutes(tree);

    await waitFor(() => expect(screen.getByText("Not available")).toBeInTheDocument());
  });

  it("renders nothing at all when no fallback is supplied", async () => {
    signedInAs("viewer");
    const { container } = renderRoutes(
      <PermissionGate roles={["admin"]}>
        <button>Destructive action</button>
      </PermissionGate>,
    );

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("admits platform_admin only where the role is listed", async () => {
    // hasRole is an exact membership check, not a hierarchy check — worth
    // pinning, because the backend's require_role DOES let platform_admin
    // bypass, and the two behaving differently is a real trap.
    signedInAs("platform_admin");
    renderRoutes(tree);

    await waitFor(() => expect(screen.getByText("Not available")).toBeInTheDocument());
  });
});
