import { Auth0Provider } from "@auth0/auth0-react";
import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import App from "./App";
import { AuthProvider } from "./contexts/AuthContext";
import "./index.css";
import { auth0Config, auth0Enabled } from "./lib/auth0Config";
import { queryClient } from "./lib/queryClient";
import { applyAccessibilitySettings, subscribeToSystemThemeChanges } from "./utils/accessibility";

function AppWithProviders() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {/* BASE_URL is "/" for root hosting and "/SentinelX/" for a GitHub
            Pages project site; without it every route 404s under the subpath.
            Vite injects it from the `base` option in vite.config.ts. */}
        <BrowserRouter basename={import.meta.env.BASE_URL}>
          <App />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

applyAccessibilitySettings();
const unsubscribeSystemTheme = subscribeToSystemThemeChanges();
window.addEventListener("beforeunload", unsubscribeSystemTheme, { once: true });

const root = createRoot(document.getElementById("root")!);

if (auth0Enabled) {
  root.render(
    <StrictMode>
      <Auth0Provider {...auth0Config}>
        <AppWithProviders />
      </Auth0Provider>
    </StrictMode>,
  );
} else {
  root.render(
    <StrictMode>
      <AppWithProviders />
    </StrictMode>,
  );
}
