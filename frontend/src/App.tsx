import { Route, Routes } from "react-router";
import { AppShell } from "./layouts/AppShell";
import { AlertsPage } from "./pages/AlertsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DevicesPage } from "./pages/DevicesPage";
import { RecoveryActionsPage } from "./pages/RecoveryActionsPage";

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="devices" element={<DevicesPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="recovery-actions" element={<RecoveryActionsPage />} />
      </Route>
    </Routes>
  );
}

export default App;