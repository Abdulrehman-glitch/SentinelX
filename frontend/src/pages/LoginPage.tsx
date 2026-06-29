import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { useAuth } from "../contexts/AuthContext";
import { ApiError } from "../lib/api";

function formatApiError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.details) {
      try {
        const parsed = JSON.parse(error.details);

        if (typeof parsed.detail === "string") {
          return parsed.detail;
        }

        if (Array.isArray(parsed.detail)) {
          return parsed.detail
            .map((item) => item.msg ?? JSON.stringify(item))
            .join(", ");
        }

        return JSON.stringify(parsed);
      } catch {
        return error.details;
      }
    }

    if (error.status === 401) {
      return "Invalid email or password.";
    }

    if (error.status === 422) {
      return "Login request does not match the backend validation format.";
    }

    return `Login failed: ${error.status} ${error.statusText}`;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Login failed. Check your credentials and try again.";
}

export function LoginPage() {
  const { login, isAuthenticated, isLoading, errorMessage } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const from =
    (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ??
    "/";

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLocalError(null);

      await login({
        email: email.trim(),
        password,
      });

      navigate(from, { replace: true });
    } catch (error) {
      setLocalError(formatApiError(error));
    }
  }

  return (
    <main className="sentinelx-console flex min-h-screen items-center justify-center px-6">
      <section className="sx-panel w-full max-w-md rounded-3xl p-8">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.28em] text-amber-400">
          SentinelX Secure Access
        </p>

        <h1 className="mt-4 text-4xl font-bold text-slate-50">Sign in</h1>

        <p className="mt-3 text-sm leading-6 text-slate-400">
          Access the monitoring console using your SentinelX credentials.
        </p>

        {(localError || errorMessage) && (
          <div className="mt-5 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
            {localError ?? errorMessage}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="text-sm font-semibold text-slate-300">Email</label>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
              type="email"
              placeholder="admin@sentinelx.com"
              autoComplete="email"
            />
          </div>

          <div>
            <label className="text-sm font-semibold text-slate-300">
              Password
            </label>
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
              type="password"
              placeholder="Enter password"
              autoComplete="current-password"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading || !email.trim() || !password}
            className="sx-button-primary w-full rounded-xl px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="mt-5 text-sm text-slate-400">
          Need a local test account?{" "}
          <Link to="/signup" className="font-semibold text-amber-400">
            Create one
          </Link>
        </p>
      </section>
    </main>
  );
}