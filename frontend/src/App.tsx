import { Route, Routes } from "react-router";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AppShell } from "./layouts/AppShell";
import { AgentSetupPage } from "./pages/AgentSetupPage";
import { AlertRulesPage } from "./pages/AlertRulesPage";
import { AlertsPage } from "./pages/AlertsPage";
import { AuditLogsPage } from "./pages/AuditLogsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DeviceCredentialsPage } from "./pages/DeviceCredentialsPage";
import { DeviceDetailPage } from "./pages/DeviceDetailPage";
import { DevicesPage } from "./pages/DevicesPage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { LoginPage } from "./pages/LoginPage";
import { MetricsExplorerPage } from "./pages/MetricsExplorerPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RecoveryActionsPage } from "./pages/RecoveryActionsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SignupPage } from "./pages/SignupPage";
import { UserManagementPage } from "./pages/UserManagementPage";

function App() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route path="signup" element={<SignupPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="devices" element={<DevicesPage />} />
          <Route path="devices/:deviceId" element={<DeviceDetailPage />} />
          <Route path="metrics" element={<MetricsExplorerPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="recovery-actions" element={<RecoveryActionsPage />} />
          <Route path="incidents" element={<IncidentsPage />} />
          <Route path="incidents/:incidentId" element={<IncidentDetailPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
        <Route element={<AppShell />}>
          <Route path="alert-rules" element={<AlertRulesPage />} />
          <Route path="audit-logs" element={<AuditLogsPage />} />
          <Route path="users" element={<UserManagementPage />} />
          <Route path="device-credentials" element={<DeviceCredentialsPage />} />
          <Route path="agent-setup" element={<AgentSetupPage />} />
        </Route>
      </Route>
    </Routes>
  );
}

export default App;