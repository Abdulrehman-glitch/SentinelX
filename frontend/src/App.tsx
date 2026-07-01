import { Navigate, Route, Routes } from "react-router";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AppShell } from "./layouts/AppShell";
import { AgentSetupPage } from "./pages/AgentSetupPage";
import { AlertRulesPage } from "./pages/AlertRulesPage";
import { AlertsPage } from "./pages/AlertsPage";
import { AnomalyCentrePage } from "./pages/AnomalyCentrePage";
import { AuditLogsPage } from "./pages/AuditLogsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DeviceCredentialsPage } from "./pages/DeviceCredentialsPage";
import { DeviceDetailPage } from "./pages/DeviceDetailPage";
import { DevicesPage } from "./pages/DevicesPage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { Auth0CallbackPage } from "./pages/Auth0CallbackPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { MetricsExplorerPage } from "./pages/MetricsExplorerPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RecoveryActionsPage } from "./pages/RecoveryActionsPage";
import { RecoveryCommandPage } from "./pages/RecoveryCommandPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SignupPage } from "./pages/SignupPage";
import { UserManagementPage } from "./pages/UserManagementPage";

function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<LandingPage />} />
      <Route path="login" element={<LoginPage />} />
      <Route path="signup" element={<SignupPage />} />
      <Route path="auth0/callback" element={<Auth0CallbackPage />} />

      {/* All authenticated users */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="devices" element={<DevicesPage />} />
          <Route path="devices/:deviceId" element={<DeviceDetailPage />} />
          <Route path="metrics" element={<MetricsExplorerPage />} />
          <Route path="anomalies" element={<AnomalyCentrePage />} />
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
  );
}

export default App;
