import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { Eye, EyeOff, ShieldCheck } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { ApiError } from "../lib/api";

function getFriendlyError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.details) {
      try {
        const parsed = JSON.parse(error.details);
        if (typeof parsed.detail === "string") return parsed.detail;
      } catch {
        return error.details;
      }
    }
    if (error.status === 409) return "A user with this email already exists.";
    if (error.status === 422) return "Invalid signup data. Check all fields.";
    if (error.status === 403) return "Signup is not permitted for this configuration.";
  }
  if (error instanceof Error) return error.message;
  return "Signup failed. Check your details and try again.";
}

export function SignupPage() {
  const { signup, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  if (isAuthenticated) return <Navigate to="/" replace />;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      setLocalError(null);
      await signup({ email: email.trim(), full_name: fullName.trim(), password, role: "viewer" });
      navigate("/", { replace: true });
    } catch (error) {
      setLocalError(getFriendlyError(error));
    }
  }

  return (
    <main
      className="flex min-h-screen items-center justify-center px-6 py-12"
      style={{ background: "var(--sx-bg)", fontFamily: "var(--font-ui)" }}
    >
      <div className="w-full max-w-[420px] sx-animate-in">
        {/* Logo */}
        <div className="mb-7 flex items-center gap-3">
          <div
            className="flex size-9 items-center justify-center rounded-xl text-xs font-black text-white"
            style={{
              background: "linear-gradient(135deg, #4f46e5, #4338ca)",
              boxShadow: "0 6px 20px rgba(79,70,229,0.35)",
            }}
          >
            SX
          </div>
          <div>
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.26em]" style={{ color: "#4f46e5" }}>
              SentinelX
            </p>
            <p className="text-sm font-bold" style={{ color: "var(--sx-text)" }}>Operations Console</p>
          </div>
        </div>

        <div className="sx-panel" style={{ padding: "2rem", borderRadius: "18px" }}>
          {/* Heading */}
          <h1 className="text-2xl font-bold" style={{ color: "var(--sx-text)" }}>
            Create your account
          </h1>
          <p className="mt-1.5 text-sm" style={{ color: "var(--sx-muted)" }}>
            Accounts are created as <strong style={{ color: "#4f46e5" }}>viewer</strong> by default.
            The first registered user becomes admin.
          </p>

          {/* Info notice */}
          <div
            className="mt-4 flex items-start gap-2.5 rounded-lg px-3.5 py-3 text-sm"
            style={{
              background: "rgba(79,70,229,0.07)",
              border: "1px solid rgba(79,70,229,0.20)",
              color: "#4338ca",
            }}
          >
            <ShieldCheck size={15} className="mt-0.5 shrink-0" />
            <span>
              Role escalation is controlled by the admin. New accounts start with read-only access.
            </span>
          </div>

          {/* Error */}
          {localError && (
            <div
              className="mt-4 rounded-lg px-4 py-3 text-sm"
              style={{
                background: "rgba(225,29,72,0.07)",
                border: "1px solid rgba(225,29,72,0.22)",
                color: "#be123c",
              }}
            >
              {localError}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label className="sx-field-label">Full name</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Jane Smith"
                autoComplete="name"
                className="sx-input"
                style={{ marginTop: "0.375rem" }}
              />
            </div>

            <div>
              <label className="sx-field-label">Email address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                className="sx-input"
                style={{ marginTop: "0.375rem" }}
              />
            </div>

            <div>
              <label className="sx-field-label">Password</label>
              <div className="relative" style={{ marginTop: "0.375rem" }}>
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="8+ characters"
                  autoComplete="new-password"
                  className="sx-input"
                  style={{ paddingRight: "2.75rem" }}
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 transition-colors"
                  style={{ color: "var(--sx-dim)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = "var(--sx-muted)")}
                  onMouseLeave={(e) => (e.currentTarget.style.color = "var(--sx-dim)")}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading || !email.trim() || !fullName.trim() || !password}
              className="sx-button-primary w-full justify-center py-2.5 text-sm"
            >
              {isLoading ? (
                <span className="flex items-center gap-2">
                  <span className="sx-spinner" />
                  Creating account…
                </span>
              ) : (
                "Create account"
              )}
            </button>
          </form>

          <p className="mt-5 text-sm" style={{ color: "var(--sx-muted)" }}>
            Already have an account?{" "}
            <Link to="/login" className="font-semibold transition-colors" style={{ color: "#4f46e5" }}>
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
