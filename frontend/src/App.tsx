import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AppShell } from "./layouts/AppShell";

// Route-level code splitting: each page (and its heavy deps — GSAP/ogl on the
// landing page, Recharts on the data pages) loads on demand instead of in one bundle.
const LandingPage = lazy(() => import("./pages/LandingPage").then((m) => ({ default: m.LandingPage })));
const LoginPage = lazy(() => import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const Auth0CallbackPage = lazy(() => import("./pages/Auth0CallbackPage").then((m) => ({ default: m.Auth0CallbackPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const DevicesPage = lazy(() => import("./pages/DevicesPage").then((m) => ({ default: m.DevicesPage })));
const DeviceDetailPage = lazy(() => import("./pages/DeviceDetailPage").then((m) => ({ default: m.DeviceDetailPage })));
const MetricsExplorerPage = lazy(() => import("./pages/MetricsExplorerPage").then((m) => ({ default: m.MetricsExplorerPage })));
const AnomalyCentrePage = lazy(() => import("./pages/AnomalyCentrePage").then((m) => ({ default: m.AnomalyCentrePage })));
const AlertsPage = lazy(() => import("./pages/AlertsPage").then((m) => ({ default: m.AlertsPage })));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage").then((m) => ({ default: m.NotificationsPage })));
const RecoveryActionsPage = lazy(() => import("./pages/RecoveryActionsPage").then((m) => ({ default: m.RecoveryActionsPage })));
const RecoveryCommandPage = lazy(() => import("./pages/RecoveryCommandPage").then((m) => ({ default: m.RecoveryCommandPage })));
const IncidentsPage = lazy(() => import("./pages/IncidentsPage").then((m) => ({ default: m.IncidentsPage })));
const IncidentDetailPage = lazy(() => import("./pages/IncidentDetailPage").then((m) => ({ default: m.IncidentDetailPage })));
const ReportsPage = lazy(() => import("./pages/ReportsPage").then((m) => ({ default: m.ReportsPage })));
const ProfilePage = lazy(() => import("./pages/ProfilePage").then((m) => ({ default: m.ProfilePage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const AnomalyPredictionsPage = lazy(() => import("./pages/AnomalyPredictionsPage").then((m) => ({ default: m.AnomalyPredictionsPage })));
const AnomalyPredictionDetailPage = lazy(() => import("./pages/AnomalyPredictionDetailPage").then((m) => ({ default: m.AnomalyPredictionDetailPage })));
const AlertRulesPage = lazy(() => import("./pages/AlertRulesPage").then((m) => ({ default: m.AlertRulesPage })));
const AuditLogsPage = lazy(() => import("./pages/AuditLogsPage").then((m) => ({ default: m.AuditLogsPage })));
const UserManagementPage = lazy(() => import("./pages/UserManagementPage").then((m) => ({ default: m.UserManagementPage })));
const DeviceCredentialsPage = lazy(() => import("./pages/DeviceCredentialsPage").then((m) => ({ default: m.DeviceCredentialsPage })));
const AgentSetupPage = lazy(() => import("./pages/AgentSetupPage").then((m) => ({ default: m.AgentSetupPage })));

// Lightweight shell-tinted fallback so chunk loads never flash a blank page.
function RouteFallback() {
  return <div className="min-h-screen" style={{ background: "var(--sx-bg)" }} aria-busy="true" />;
}

function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<LandingPage />} />
        <Route path="login" element={<LoginPage />} />
        {/* Public self-signup is disabled — accounts are created by an org admin
            after login (see User Management). Any old links fall back to login. */}
        <Route path="signup" element={<Navigate to="/login" replace />} />
        <Route path="auth0/callback" element={<Auth0CallbackPage />} />

        {/* All authenticated users */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="devices" element={<DevicesPage />} />
            <Route path="devices/:deviceId" element={<DeviceDetailPage />} />
            <Route path="metrics" element={<MetricsExplorerPage />} />
            <Route path="anomalies" element={<AnomalyCentrePage />} />
            <Route path="anomaly-predictions" element={<AnomalyPredictionsPage />} />
            <Route path="anomaly-predictions/:predictionId" element={<AnomalyPredictionDetailPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="recovery-actions" element={<RecoveryActionsPage />} />
            <Route path="recovery-command" element={<RecoveryCommandPage />} />
            <Route path="incidents" element={<IncidentsPage />} />
            <Route path="incidents/:incidentId" element={<IncidentDetailPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Route>

        {/* Admin / Owner / Platform Admin only */}
        <Route element={<ProtectedRoute allowedRoles={["admin", "owner", "platform_admin"]} />}>
          <Route element={<AppShell />}>
            <Route path="alert-rules" element={<AlertRulesPage />} />
            <Route path="audit-logs" element={<AuditLogsPage />} />
            {/* Security logs intentionally NOT exposed on the frontend — backend/forensics only. */}
            <Route path="users" element={<UserManagementPage />} />
            <Route path="device-credentials" element={<DeviceCredentialsPage />} />
            <Route path="agent-setup" element={<AgentSetupPage />} />
          </Route>
        </Route>

        {/* Legacy redirect */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

export default App;
