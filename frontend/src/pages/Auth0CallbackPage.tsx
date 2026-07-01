import { useAuth0 } from "@auth0/auth0-react";
import { useEffect } from "react";
import { Navigate, useNavigate } from "react-router";
import { auth0Enabled } from "../lib/auth0Config";

function Auth0CallbackInner() {
  const { isLoading, isAuthenticated, error } = useAuth0();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading) {
      if (isAuthenticated) {
        navigate("/dashboard", { replace: true });
      } else if (error) {
        navigate("/login", { replace: true });
      }
    }
  }, [isLoading, isAuthenticated, error, navigate]);

  if (error) {
    return (
      <main
        className="flex min-h-screen items-center justify-center"
        style={{ background: "var(--sx-bg)", color: "var(--sx-text)", fontFamily: "var(--font-ui)" }}
      >
        <div className="text-center">
          <p className="text-lg font-semibold" style={{ color: "#e11d48" }}>Sign-in failed</p>
          <p className="mt-2 text-sm" style={{ color: "#5a6678" }}>{error.message}</p>
        </div>
      </main>
    );
  }

  return (
    <main
      className="flex min-h-screen items-center justify-center"
      style={{ background: "var(--sx-bg)", color: "var(--sx-text)", fontFamily: "var(--font-ui)" }}
    >
      <div className="flex flex-col items-center gap-4">
        <div
          className="h-8 w-8 rounded-full border-2 animate-spin"
          style={{ borderColor: "rgba(79,70,229,0.25)", borderTopColor: "#4f46e5" }}
        />
        <p className="text-sm" style={{ color: "#5a6678" }}>Completing sign-in…</p>
      </div>
    </main>
  );
}

export function Auth0CallbackPage() {
  if (!auth0Enabled) {
    return <Navigate to="/login" replace />;
  }
  return <Auth0CallbackInner />;
}
