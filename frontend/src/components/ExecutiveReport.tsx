import { useMemo } from "react";
import { Badge } from "./Badge";
import { useAlertRulesQuery } from "../hooks/useAlertRulesQuery";
import { useAlertsQuery } from "../hooks/useAlertsQuery";
import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";
import { useDevicesQuery } from "../hooks/useDevicesQuery";
import { useIncidentsQuery } from "../hooks/useIncidentsQuery";
import { useOverviewQuery } from "../hooks/useOverviewQuery";
import { useRecoveryActionsQuery } from "../hooks/useRecoveryActionsQuery";
import { downloadCsv } from "../utils/csv";

function isUnresolvedAlert(alert: { resolved?: boolean; is_resolved?: boolean }) {
  return !(alert.resolved ?? alert.is_resolved ?? false);
}

function buildReportText(report: {
  generatedAt: string;
  devicesTotal: number;
  onlineDevices: number;
  offlineDevices: number;
  unresolvedAlerts: number;
  openIncidents: number;
  recoveryActions: number;
  alertRules: number;
  auditLogs: number;
}) {
  return `SentinelX Operational Report
Generated: ${report.generatedAt}

Fleet
- Total devices: ${report.devicesTotal}
- Online devices: ${report.onlineDevices}
- Offline devices: ${report.offlineDevices}

Operations
- Unresolved alerts: ${report.unresolvedAlerts}
- Open incidents: ${report.openIncidents}
- Recovery actions logged: ${report.recoveryActions}
- Alert rules configured: ${report.alertRules}
- Audit logs recorded: ${report.auditLogs}

Interpretation
SentinelX currently provides device monitoring, metric visualisation, alert review, recovery action logging, incident tracking, auditability, RBAC, agent credentials, notifications, topology mapping and anomaly investigation.`;
}

function downloadText(filename: string, text: string) {
  const blob = new Blob([text], {
    type: "text/plain;charset=utf-8;",
  });

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  link.click();

  URL.revokeObjectURL(url);
}

export function ExecutiveReport() {
  const overviewQuery = useOverviewQuery();
  const devicesQuery = useDevicesQuery();
  const alertsQuery = useAlertsQuery();
  const incidentsQuery = useIncidentsQuery();
  const recoveryActionsQuery = useRecoveryActionsQuery();
  const alertRulesQuery = useAlertRulesQuery();
  const auditLogsQuery = useAuditLogsQuery();

  const report = useMemo(() => {
    const devices = devicesQuery.data ?? [];
    const alerts = alertsQuery.data ?? [];
    const incidents = incidentsQuery.data ?? [];
    const recoveryActions = recoveryActionsQuery.data ?? [];
    const alertRules = alertRulesQuery.data ?? [];
    const auditLogs = auditLogsQuery.data ?? [];

    return {
      generatedAt: new Date().toLocaleString(),
      devicesTotal: overviewQuery.data?.devices.total ?? devices.length,
      onlineDevices:
        overviewQuery.data?.devices.online ??
        devices.filter((device) => device.status?.toLowerCase() === "online").length,
      offlineDevices:
        overviewQuery.data?.devices.offline ??
        devices.filter((device) => device.status?.toLowerCase() === "offline").length,
      unresolvedAlerts:
        overviewQuery.data?.alerts.unresolved ??
        alerts.filter(isUnresolvedAlert).length,
      openIncidents:
        overviewQuery.data?.incidents?.open ??
        incidents.filter((incident) => incident.status !== "resolved").length,
      recoveryActions:
        overviewQuery.data?.recovery_actions.total ?? recoveryActions.length,
      alertRules: overviewQuery.data?.alert_rules?.total ?? alertRules.length,
      auditLogs: overviewQuery.data?.audit_logs?.total ?? auditLogs.length,
    };
  }, [
    overviewQuery.data,
    devicesQuery.data,
    alertsQuery.data,
    incidentsQuery.data,
    recoveryActionsQuery.data,
    alertRulesQuery.data,
    auditLogsQuery.data,
  ]);

  async function refreshAll() {
    await Promise.all([
      overviewQuery.refetch(),
      devicesQuery.refetch(),
      alertsQuery.refetch(),
      incidentsQuery.refetch(),
      recoveryActionsQuery.refetch(),
      alertRulesQuery.refetch(),
      auditLogsQuery.refetch(),
    ]);
  }

  function exportCsv() {
    downloadCsv("sentinelx-operational-report.csv", [
      {
        generated_at: report.generatedAt,
        devices_total: report.devicesTotal,
        online_devices: report.onlineDevices,
        offline_devices: report.offlineDevices,
        unresolved_alerts: report.unresolvedAlerts,
        open_incidents: report.openIncidents,
        recovery_actions: report.recoveryActions,
        alert_rules: report.alertRules,
        audit_logs: report.auditLogs,
      },
    ]);
  }

  function exportText() {
    downloadText("sentinelx-operational-report.txt", buildReportText(report));
  }

  const riskLevel =
    report.unresolvedAlerts > 0 || report.openIncidents > 0
      ? report.unresolvedAlerts > 3 || report.openIncidents > 2
        ? "critical"
        : "warning"
      : "stable";

  return (
    <>
      <section className="sx-panel rounded-2xl p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-50">
              Executive Summary
            </h2>

            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
              Evidence-ready operational summary for demos, reporting, and final
              project evaluation.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge
              tone={
                riskLevel === "critical"
                  ? "red"
                  : riskLevel === "warning"
                    ? "amber"
                    : "green"
              }
            >
              {riskLevel}
            </Badge>

            <button
              type="button"
              onClick={refreshAll}
              className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold"
            >
              Refresh
            </button>

            <button
              type="button"
              onClick={exportCsv}
              className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold"
            >
              Export CSV
            </button>

            <button
              type="button"
              onClick={exportText}
              className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold"
            >
              Export report
            </button>
          </div>
        </div>
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="sx-panel rounded-2xl p-5">
          <p className="text-sm font-semibold text-slate-400">Fleet Size</p>
          <p className="mt-3 text-4xl font-bold text-slate-50">
            {report.devicesTotal}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            {report.onlineDevices} online · {report.offlineDevices} offline
          </p>
        </article>

        <article className="sx-panel rounded-2xl p-5">
          <p className="text-sm font-semibold text-slate-400">Unresolved Alerts</p>
          <p className="mt-3 text-4xl font-bold text-violet-300">
            {report.unresolvedAlerts}
          </p>
        </article>

        <article className="sx-panel rounded-2xl p-5">
          <p className="text-sm font-semibold text-slate-400">Open Incidents</p>
          <p className="mt-3 text-4xl font-bold text-rose-300">
            {report.openIncidents}
          </p>
        </article>

        <article className="sx-panel rounded-2xl p-5">
          <p className="text-sm font-semibold text-slate-400">Audit Events</p>
          <p className="mt-3 text-4xl font-bold text-slate-50">
            {report.auditLogs}
          </p>
        </article>
      </section>

      <section className="sx-panel mt-8 rounded-2xl p-5">
        <h2 className="text-lg font-bold text-slate-50">
          Project Capability Coverage
        </h2>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {[
            "Authentication and RBAC",
            "Device monitoring and agent onboarding",
            "Telemetry charts and Metrics Explorer",
            "Alerts and alert rules",
            "Recovery actions and safe playbooks",
            "Incidents and timeline investigation",
            "Audit logs and traceability",
            "Notification Centre",
            "Topology map",
            "Anomaly Centre",
            "Accessibility settings",
            "Evidence-ready reports",
          ].map((item) => (
            <div
              key={item}
              className="rounded-xl border border-white/[0.056] bg-black/25 p-4 text-sm font-semibold text-slate-300"
            >
              {item}
            </div>
          ))}
        </div>
      </section>
    </>
  );
}