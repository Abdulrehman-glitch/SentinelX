import { Auth0Provider } from "@auth0/auth0-react";
import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import App from "./App";
import { AgentationDevTools } from "./components/AgentationDevTools";
import { AuthProvider } from "./contexts/AuthContext";
import "./index.css";
import { auth0Config, auth0Enabled } from "./lib/auth0Config";
import { queryClient } from "./lib/queryClient";
import { applyAccessibilitySettings, subscribeToSystemThemeChanges } from "./utils/accessibility";

function AppWithProviders() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <App />
          <AgentationDevTools />
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
