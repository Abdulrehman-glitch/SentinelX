import { useAuth0 } from "@auth0/auth0-react";
import { Activity, AlertTriangle, Eye, EyeOff, Shield, Zap, type LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { useAuth } from "../contexts/AuthContext";
import { ApiError } from "../lib/api";
import { auth0Enabled } from "../lib/auth0Config";
import LineWaves from "../components/LineWaves";

function formatApiError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.details) {
      try {
        const parsed = JSON.parse(error.details);
        if (typeof parsed.detail === "string") return parsed.detail;
        if (Array.isArray(parsed.detail))
          return parsed.detail.map((item: { msg?: string }) => item.msg ?? JSON.stringify(item)).join(", ");
        return JSON.stringify(parsed);
      } catch {
        return error.details;
      }
    }
    if (error.status === 401) return "Invalid email or password.";
    if (error.status === 422) return "Invalid credentials format.";
    return `Login failed: ${error.status} ${error.statusText}`;
  }
  if (error instanceof Error) return error.message;
  return "Login failed. Check your credentials and try again.";
}

const features: { icon: LucideIcon; label: string }[] = [
  { icon: Activity, label: "Real-time device monitoring" },
  { icon: AlertTriangle, label: "Intelligent alert detection" },
  { icon: Zap, label: "Automated recovery logging" },
  { icon: Shield, label: "Role-based access control" },
];

function Auth0LoginButton() {
  const { loginWithRedirect, isLoading } = useAuth0();
  return (
    <button
      type="button"
      disabled={isLoading}
      onClick={() => loginWithRedirect()}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "10px",
        width: "100%",
        padding: "10px 0",
        borderRadius: "10px",
        border: "1px solid rgba(200,16,46,0.30)",
        background: "rgba(200,16,46,0.07)",
        color: "#c8102e",
        fontSize: "0.9rem",
        fontWeight: 600,
        cursor: isLoading ? "not-allowed" : "pointer",
        opacity: isLoading ? 0.6 : 1,
        transition: "all 0.15s",
        fontFamily: "inherit",
      }}
      onMouseEnter={(e) => { if (!isLoading) { e.currentTarget.style.background = "rgba(200,16,46,0.13)"; e.currentTarget.style.borderColor = "rgba(200,16,46,0.50)"; } }}
      onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(200,16,46,0.07)"; e.currentTarget.style.borderColor = "rgba(200,16,46,0.30)"; }}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M21.98 7.448L18.2 13.648l-3.78-6.2h-4.84L5.8 13.648 2.02 7.448H0l5.8 9.104h4.84L14.42 10.4l3.78 6.152H23L17.2 7.448h-2.78z" fill="currentColor"/>
      </svg>
      Continue with Auth0
    </button>
  );
}

export function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});

  // On a genuine hard reload of /login (location.key === "default"), return to
  // the welcome page so the intro replays; in-app nav (landing CTA) must not.
  useEffect(() => {
    const [nav] = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
    if (nav?.type === "reload" && location.key === "default" && !isAuthenticated) {
      navigate("/", { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  }, []);

  const from =
    (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/";

  if (isAuthenticated) return <Navigate to="/" replace />;

  function validate(): boolean {
    const next: { email?: string; password?: string } = {};
    const trimmedEmail = email.trim();
    if (!trimmedEmail) next.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail))
      next.email = "Enter a valid email address.";
    if (!password) next.password = "Password is required.";
    else if (password.length < 6) next.password = "Password must be at least 6 characters.";
    setFieldErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLocalError(null);
    if (!validate()) return;
    try {
      await login({ email: email.trim(), password });
      navigate(from, { replace: true });
    } catch (error) {
      setLocalError(formatApiError(error));
    }
  }

  const fieldErrorStyle = { color: "#dc2626", fontSize: "0.75rem", marginTop: "0.3rem" } as const;

  return (
    <main
      className="relative flex min-h-screen items-stretch overflow-hidden"
      style={{ background: "var(--sx-bg)", fontFamily: "var(--font-ui)" }}
    >
      {/* Cursor-interactive animated background */}
      <div className="pointer-events-none absolute inset-0 z-0" aria-hidden="true">
        <div className="pointer-events-auto h-full w-full">
          <LineWaves
            speed={0.26}
            brightness={0.5}
            warpIntensity={1.0}
            rotation={-45}
            color1="#d81f3d"
            color2="#ef5d6e"
            color3="#c8102e"
            enableMouseInteraction
            mouseInfluence={2.0}
          />
        </div>
      </div>

      {/* Left brand panel */}
      <div
        className="relative z-10 hidden flex-col justify-between overflow-hidden p-10 lg:flex lg:w-[420px] xl:w-[480px]"
        style={{
          background: "linear-gradient(160deg, #14171e 0%, #0b0d12 58%, #08090d 100%)",
        }}
      >
        {/* aurora glow */}
        <div
          aria-hidden="true"
          style={{
            position: "absolute", inset: 0, pointerEvents: "none",
            background:
              "radial-gradient(540px 420px at 18% 8%, rgba(200,16,46,0.20), transparent 60%), radial-gradient(480px 360px at 90% 100%, rgba(198,201,206,0.10), transparent 60%)",
          }}
        />
        <div className="relative">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <img
              src="/brand/sentinelx-mark.png"
              alt=""
              className="size-10 rounded-xl object-cover"
              style={{ border: "1px solid rgba(255,255,255,0.16)", boxShadow: "0 6px 20px rgba(200,16,46,0.25)" }}
            />
            <div>
              <p
                className="text-[11px]"
                style={{ fontFamily: "var(--font-brand)", color: "#f2f3f5", letterSpacing: "0.06em" }}
              >
                Sentinel<span style={{ color: "#ff2d44" }}>X</span>
              </p>
              <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.24em]" style={{ color: "rgba(255,255,255,0.55)" }}>
                Operations Console
              </p>
            </div>
          </div>

          {/* Hero text */}
          <div className="mt-16">
            <h1
              className="text-3xl leading-snug text-white"
              style={{ fontFamily: "var(--font-brand)" }}
            >
              Detect.
              <br />
              Defend.
              <br />
              <span style={{ color: "#ff2d44" }}>Recover.</span>
            </h1>
            <p className="mt-5 text-[0.9375rem] leading-relaxed" style={{ color: "rgba(255,255,255,0.72)" }}>
              Monitor fleets, detect anomalies, and orchestrate recovery — all from a single
              unified console.
            </p>
          </div>

          {/* Feature list */}
          <ul className="mt-10 space-y-4">
            {features.map(({ icon: Icon, label }) => (
              <li key={label} className="flex items-center gap-3">
                <div
                  className="flex size-8 shrink-0 items-center justify-center rounded-lg"
                  style={{ background: "rgba(255,255,255,0.14)", border: "1px solid rgba(255,255,255,0.24)" }}
                >
                  <Icon size={15} style={{ color: "#fff" }} />
                </div>
                <span className="text-sm font-medium" style={{ color: "rgba(255,255,255,0.86)" }}>
                  {label}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* Footer note */}
        <p className="relative font-mono text-[10px]" style={{ color: "rgba(255,255,255,0.5)" }}>
          Distributed monitoring &amp; self-healing platform
        </p>
      </div>

      {/* Right login panel */}
      <div className="relative z-10 flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-[400px] sx-animate-in">
          {/* Mobile logo */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <img
              src="/brand/sentinelx-mark.png"
              alt=""
              className="size-9 rounded-xl object-cover"
              style={{ boxShadow: "0 4px 14px rgba(200,16,46,0.30)" }}
            />
            <div>
              <p
                className="text-[11px]"
                style={{ fontFamily: "var(--font-brand)", color: "var(--sx-text)", letterSpacing: "0.06em" }}
              >
                Sentinel<span style={{ color: "#c8102e" }}>X</span>
              </p>
              <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.22em]" style={{ color: "var(--sx-muted)" }}>
                Operations Console
              </p>
            </div>
          </div>

          <div className="sx-panel" style={{ padding: "2rem", borderRadius: "18px" }}>
            <div>
              <h2 className="text-2xl font-bold" style={{ color: "var(--sx-text)" }}>
                Welcome back
              </h2>
              <p className="mt-1.5 text-sm" style={{ color: "var(--sx-muted)" }}>
                Sign in to access the monitoring console.
              </p>
            </div>

            {localError && (
              <div
                className="mt-5 rounded-lg px-4 py-3 text-sm"
                style={{
                  background: "rgba(225,29,72,0.07)",
                  border: "1px solid rgba(225,29,72,0.22)",
                  color: "#be123c",
                }}
              >
                {localError}
              </div>
            )}

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <div>
                <label htmlFor="login-email" className="sx-field-label">
                  Email address
                </label>
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); if (fieldErrors.email) setFieldErrors((f) => ({ ...f, email: undefined })); }}
                  placeholder="you@example.com"
                  autoComplete="email"
                  aria-invalid={!!fieldErrors.email}
                  className="sx-input"
                  style={{ marginTop: "0.375rem", borderColor: fieldErrors.email ? "#dc2626" : undefined }}
                />
                {fieldErrors.email && <p style={fieldErrorStyle}>{fieldErrors.email}</p>}
              </div>

              <div>
                <label htmlFor="login-password" className="sx-field-label">
                  Password
                </label>
                <div className="relative" style={{ marginTop: "0.375rem" }}>
                  <input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); if (fieldErrors.password) setFieldErrors((f) => ({ ...f, password: undefined })); }}
                    placeholder="Enter password"
                    autoComplete="current-password"
                    aria-invalid={!!fieldErrors.password}
                    className="sx-input"
                    style={{ paddingRight: "2.75rem", borderColor: fieldErrors.password ? "#dc2626" : undefined }}
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
                {fieldErrors.password && <p style={fieldErrorStyle}>{fieldErrors.password}</p>}
              </div>

              <button
                type="submit"
                disabled={isLoading || !email.trim() || !password}
                className="sx-button-primary w-full justify-center py-2.5 text-sm"
                style={{ marginTop: "0.25rem" }}
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <span className="sx-spinner" />
                    Signing in…
                  </span>
                ) : (
                  "Sign in"
                )}
              </button>
            </form>

            {auth0Enabled && (
              <>
                <div className="flex items-center gap-3 mt-5" style={{ color: "var(--sx-dim)" }}>
                  <div style={{ flex: 1, height: "1px", background: "var(--sx-border)" }} />
                  <span style={{ fontSize: "0.75rem", fontWeight: 500, whiteSpace: "nowrap" }}>or continue with</span>
                  <div style={{ flex: 1, height: "1px", background: "var(--sx-border)" }} />
                </div>
                <div className="mt-3">
                  <Auth0LoginButton />
                </div>
              </>
            )}

            <p className="mt-5 text-xs leading-relaxed" style={{ color: "var(--sx-dim)" }}>
              Accounts are provisioned by your organisation's administrator.
              Contact your admin if you need access.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
