import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import App from "./App";
import { AuthProvider } from "./contexts/AuthContext";
import "./index.css";
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

root.render(
  <StrictMode>
    <AppWithProviders />
  </StrictMode>,
);
