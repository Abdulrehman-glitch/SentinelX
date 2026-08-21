import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "../LoginPage";
import { AuthProvider } from "../../contexts/AuthContext";
import { setSessionEndedHandler } from "../../lib/api";
import { authStorage, CSRF_COOKIE_NAME } from "../../lib/authStorage";
import { expectNoAxeViolations, jsonResponse, makeQueryClient, makeUser } from "../../test/utils";

// The login page carries a decorative WebGL background. jsdom has no GL
// context, and the animation is irrelevant to every assertion here — mocking
// it keeps these tests about behaviour rather than about canvas support.
vi.mock("../../components/LineWaves", () => ({
  default: () => null,
}));

function fetchMock() {
  return globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
}

const SESSION_BODY = {
  access_token: "fresh-access-token",
  token_type: "bearer",
  expires_in: 900,
  user: makeUser(),
};

function renderLogin() {
  const queryClient = makeQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/dashboard" element={<div>Dashboard</div>} />
            <Route path="/" element={<div>Landing</div>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

/** Settle the AuthProvider's cold-start refresh before interacting. */
async function renderSignedOut() {
  fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "No active session." }, 401));
  const view = renderLogin();
  await screen.findByLabelText(/email/i);
  return view;
}

async function submitCredentials(password = "SentinelX2026!") {
  await userEvent.type(screen.getByLabelText(/email/i), "ops@technova.io");
  await userEvent.type(screen.getByLabelText(/^password$/i), password);
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
}

beforeEach(() => {
  authStorage.clearToken();
  setSessionEndedHandler(null);
  document.cookie = `${CSRF_COOKIE_NAME}=csrf-token`;
});

describe("sign-in form", () => {
  it("labels both fields so they are reachable by name", async () => {
    await renderSignedOut();

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("masks the password field", async () => {
    await renderSignedOut();
    expect(screen.getByLabelText(/^password$/i)).toHaveAttribute("type", "password");
  });

  it("submits the typed credentials", async () => {
    await renderSignedOut();
    fetchMock().mockResolvedValueOnce(jsonResponse(SESSION_BODY));

    await submitCredentials();

    await waitFor(() => expect(fetchMock()).toHaveBeenCalledTimes(2));

    const [url, init] = fetchMock().mock.calls[1];
    expect(String(url)).toContain("/auth/login");
    expect(JSON.parse(init.body)).toEqual({
      email: "ops@technova.io",
      password: "SentinelX2026!",
    });
  });

  it("can be completed with the keyboard alone", async () => {
    // Tab order and Enter-to-submit are the parts a mouse-driven test never
    // exercises, and the parts most likely to break silently.
    await renderSignedOut();
    fetchMock().mockResolvedValueOnce(jsonResponse(SESSION_BODY));

    screen.getByLabelText(/email/i).focus();
    await userEvent.keyboard("ops@technova.io");
    await userEvent.tab();
    await userEvent.keyboard("SentinelX2026!");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => expect(fetchMock()).toHaveBeenCalledTimes(2));
    expect(String(fetchMock().mock.calls[1][0])).toContain("/auth/login");
  });

  it("does not call the API when the form is empty", async () => {
    await renderSignedOut();

    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    // Only the cold-start refresh should have happened.
    expect(fetchMock()).toHaveBeenCalledTimes(1);
  });
});

describe("failure states", () => {
  it("shows the server's reason for a rejected sign-in", async () => {
    await renderSignedOut();
    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "Invalid email or password." }, 401));

    await submitCredentials("WrongPassword1!");

    expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument();
  });

  it("explains a rate limit instead of looking broken", async () => {
    await renderSignedOut();
    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "" }, 429));

    await submitCredentials();

    expect(await screen.findByText(/too many requests/i)).toBeInTheDocument();
  });

  it("reports a deactivated account rather than a generic failure", async () => {
    await renderSignedOut();
    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "User account is inactive." }, 403));

    await submitCredentials();

    expect(await screen.findByText(/inactive/i)).toBeInTheDocument();
  });

  it("stays usable when the backend is unreachable", async () => {
    await renderSignedOut();
    fetchMock().mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await submitCredentials();

    // The button must return to an enabled state; a permanently spinning
    // button after a network blip is a support ticket.
    await waitFor(() => expect(screen.getByRole("button", { name: /sign in/i })).toBeEnabled());
  });

  it("never renders the submitted password back into the DOM", async () => {
    await renderSignedOut();
    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "Invalid email or password." }, 401));

    await submitCredentials("SuperSecret123!");

    await screen.findByText(/invalid email or password/i);
    expect(document.body.textContent).not.toContain("SuperSecret123!");
  });
});

describe("accessibility", () => {
  it("has no machine-detectable violations at rest", async () => {
    const { container } = await renderSignedOut();
    await expectNoAxeViolations(container);
  });

  it("has no machine-detectable violations while showing an error", async () => {
    const { container } = await renderSignedOut();
    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "Invalid email or password." }, 401));

    await submitCredentials("WrongPassword1!");
    await screen.findByText(/invalid email or password/i);

    await expectNoAxeViolations(container);
  });
});
