import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { useAuth } from "../contexts/AuthContext";

export function LoginPage() {
  const { login, isAuthenticated, isLoading, errorMessage } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("admin@sentinelx.local");
  const [password, setPassword] = useState("Password123!");
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
      await login({ email, password });
      navigate(from, { replace: true });
    } catch {
      setLocalError("Login failed. Check your credentials and try again.");
    }
  }

  return (
    <main className="sentinelx-console flex min-h-screen items-center justify-center px-6">
      <section className="sx-panel w-full max-w-md rounded-3xl p-8">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.28em] text-amber-400">
          SentinelX Secure Access
        </p>

        <h1 className="mt-4 text-4xl font-bold text-slate-50">
          Sign in
        </h1>

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
            />
          </div>

          <div>
            <label className="text-sm font-semibold text-slate-300">Password</label>
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
              type="password"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="sx-button-primary w-full rounded-xl px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}