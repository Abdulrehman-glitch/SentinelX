import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { useAuth } from "../contexts/AuthContext";
import { ApiError } from "../lib/api";
import type { UserRole } from "../types/api";

function getFriendlyError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.details) {
      return error.details;
    }

    if (error.status === 409) {
      return "A user with this email already exists.";
    }

    if (error.status === 422) {
      return "The signup form does not match the backend validation rules.";
    }

    if (error.status === 403) {
      return "Signup is not allowed for this role or endpoint.";
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Signup failed. Check details and try again.";
}

export function SignupPage() {
  const { signup, isAuthenticated, isLoading, errorMessage } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("testuser1@sentinelx.com");
  const [fullName, setFullName] = useState("Test User");
  const [password, setPassword] = useState("Password123!");
  const [role, setRole] = useState<UserRole>("viewer");
  const [localError, setLocalError] = useState<string | null>(null);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLocalError(null);

      await signup({
        email,
        full_name: fullName,
        password,
        role,
      });

      navigate("/", { replace: true });
    } catch (error) {
      setLocalError(getFriendlyError(error));
    }
  }

  return (
    <main className="sentinelx-console flex min-h-screen items-center justify-center px-6">
      <section className="sx-panel w-full max-w-lg rounded-3xl p-8">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.28em] text-amber-400">
          SentinelX Registration
        </p>

        <h1 className="mt-4 text-4xl font-bold text-slate-50">
          Create account
        </h1>

        <p className="mt-3 text-sm leading-6 text-slate-400">
          Create a SentinelX user for local development and role testing.
        </p>

        {(localError || errorMessage) && (
          <div className="mt-5 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
            {localError ?? errorMessage}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 grid gap-4">
          <div>
            <label className="text-sm font-semibold text-slate-300">
              Full name
            </label>
            <input
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
            />
          </div>

          <div>
            <label className="text-sm font-semibold text-slate-300">
              Email
            </label>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
              type="email"
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
            />
          </div>

          <div>
            <label className="text-sm font-semibold text-slate-300">
              Role
            </label>
            <select
              value={role}
              onChange={(event) => setRole(event.target.value as UserRole)}
              className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
            >
              <option value="admin">admin</option>
              <option value="engineer">engineer</option>
              <option value="viewer">viewer</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="sx-button-primary rounded-xl px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading ? "Creating..." : "Create account"}
          </button>
        </form>

        <p className="mt-5 text-sm text-slate-400">
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-amber-400">
            Sign in
          </Link>
        </p>
      </section>
    </main>
  );
}