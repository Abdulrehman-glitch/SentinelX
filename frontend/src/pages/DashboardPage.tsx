import { AlertsTable } from "../components/AlertsTable";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { DashboardMetricPreview } from "../components/DashboardMetricPreview";
import { DevicesTable } from "../components/DevicesTable";
import { FleetHealthPanel } from "../components/FleetHealthPanel";
import { OperationalModulesPanel } from "../components/OperationalModulesPanel";
import { OperationsSnapshot } from "../components/OperationsSnapshot";
import { RecentAlertsPanel } from "../components/RecentAlertsPanel";
import { RecentRecoveryActionsPanel } from "../components/RecentRecoveryActionsPanel";
import { RecoveryActionsTable } from "../components/RecoveryActionsTable";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAlertRulesQuery } from "../hooks/useAlertRulesQuery";
import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";
import { useDashboardData } from "../hooks/useDashboardData";
import { useDeviceLatestMetricsQuery } from "../hooks/useDeviceLatestMetricsQuery";
import { useDeviceMetricHistoryQuery } from "../hooks/useDeviceMetricHistoryQuery";
import { useIncidentsQuery } from "../hooks/useIncidentsQuery";
import { useResolveAlertMutation } from "../hooks/useResolveAlertMutation";
import { API_BASE_URL } from "../lib/api";

function getDeviceId(device?: { id?: string; device_id?: string }) {
  return device?.id ?? device?.device_id ?? "";
}

export function DashboardPage() {
  const {
    overview,
    health,
    devices,
    alerts,
    recoveryActions,
    isLoading,
    isFetching,
    error,
    refetchAll,
  } = useDashboardData();

  const incidentsQuery = useIncidentsQuery();
  const auditLogsQuery = useAuditLogsQuery();
  const alertRulesQuery = useAlertRulesQuery();

  const resolveAlertMutation = useResolveAlertMutation();

  const selectedDevice = devices[0] ?? null;
  const selectedDeviceId = getDeviceId(selectedDevice);

  const selectedDeviceLatestMetricsQuery =
    useDeviceLatestMetricsQuery(selectedDeviceId);

  const selectedDeviceMetricHistoryQuery =
    useDeviceMetricHistoryQuery(selectedDeviceId, 50);

  const errorMessage =
    error instanceof Error
      ? error.message
      : error
        ? "Unknown error while loading dashboard data."
        : null;

  const resolvingAlertId =
    typeof resolveAlertMutation.variables === "string"
      ? resolveAlertMutation.variables
      : null;

  async function refreshAllDashboardData() {
    await Promise.all([
      refetchAll(),
      incidentsQuery.refetch(),
      auditLogsQuery.refetch(),
      alertRulesQuery.refetch(),
      selectedDeviceLatestMetricsQuery.refetch(),
      selectedDeviceMetricHistoryQuery.refetch(),
    ]);
  }

  const dashboardIsFetching =
    isFetching ||
    incidentsQuery.isFetching ||
    auditLogsQuery.isFetching ||
    alertRulesQuery.isFetching ||
    selectedDeviceLatestMetricsQuery.isFetching ||
    selectedDeviceMetricHistoryQuery.isFetching;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Command Center"
          title="Operations Overview"
          description="Central monitoring view for device availability, telemetry trends, incidents, alert rules, audit logs, unresolved alerts, and recovery actions."
        >
          <button
            type="button"
            onClick={refreshAllDashboardData}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60"
            disabled={dashboardIsFetching}
          >
            {dashboardIsFetching ? "Refreshing..." : "Refresh data"}
          </button>

          <p className="text-xs text-slate-500">
            API: <span className="font-medium text-slate-300">{API_BASE_URL}</span>
          </p>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
            <p className="font-semibold">Frontend operation failed.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <section className="mb-8 grid gap-4 md:grid-cols-2">
          <StatusBadge
            label="Backend API"
            status={health?.api_status ?? "offline"}
          />

          <StatusBadge
            label="PostgreSQL Database"
            status={health?.database_status ?? "offline"}
          />
        </section>

        {isLoading && !overview ? (
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div
                key={index}
                className="h-36 animate-pulse rounded-2xl border border-slate-800 bg-slate-900/60"
              />
            ))}
          </section>
        ) : (
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <StatCard
              title="Total Devices"
              value={overview?.devices.total ?? 0}
              description="Registered monitored machines and agents."
            />

            <StatCard
              title="Unresolved Alerts"
              value={overview?.alerts.unresolved ?? 0}
              description="Warning or critical alerts waiting for resolution."
            />

            <StatCard
              title="Open Incidents"
              value={
                overview?.incidents?.open ??
                (incidentsQuery.data ?? []).filter(
                  (incident) => incident.status !== "resolved",
                ).length
              }
              description="Operational incidents still requiring attention."
            />

            <StatCard
              title="System Metrics"
              value={overview?.metrics.total ?? 0}
              description="Stored CPU, memory, and disk telemetry records."
            />

            <StatCard
              title="Alert Rules"
              value={overview?.alert_rules?.total ?? alertRulesQuery.data?.length ?? 0}
              description="Configured threshold rules for telemetry alerts."
            />

            <StatCard
              title="Audit Logs"
              value={overview?.audit_logs?.total ?? auditLogsQuery.data?.length ?? 0}
              description="Traceable records of system activity."
            />
          </section>
        )}

        <OperationsSnapshot
          overview={overview}
          devices={devices}
          alerts={alerts}
          recoveryActions={recoveryActions}
        />

        <OperationalModulesPanel
          incidents={incidentsQuery.data ?? []}
          auditLogs={auditLogsQuery.data ?? []}
          alertRules={alertRulesQuery.data ?? []}
        />

        <DashboardMetricPreview
          device={selectedDevice}
          latestMetrics={selectedDeviceLatestMetricsQuery.data ?? null}
          metricHistory={selectedDeviceMetricHistoryQuery.data ?? []}
        />

        <section className="mt-8 grid gap-6 xl:grid-cols-2">
          <FleetHealthPanel overview={overview} devices={devices} />

          <RecentAlertsPanel
            alerts={alerts}
            resolvingAlertId={resolvingAlertId}
            onResolveAlert={resolveAlertMutation.mutate}
          />
        </section>

        <section className="mt-8">
          <RecentRecoveryActionsPanel recoveryActions={recoveryActions} />
        </section>

        <DevicesTable devices={devices} />

        <AlertsTable
          alerts={alerts}
          resolvingAlertId={resolvingAlertId}
          onResolveAlert={resolveAlertMutation.mutate}
        />

        <RecoveryActionsTable recoveryActions={recoveryActions} />

        <footer className="mt-8 rounded-2xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-400">
          <p>
            Service:{" "}
            <span className="font-semibold text-slate-100">
              {health?.service ?? "Unknown"}
            </span>
          </p>

          <p className="mt-1">
            Environment:{" "}
            <span className="font-semibold text-slate-100">
              {health?.environment ?? "Unknown"}
            </span>{" "}
            | Version:{" "}
            <span className="font-semibold text-slate-100">
              {health?.version ?? "Unknown"}
            </span>
          </p>

          <p className="mt-1">
            Cache:{" "}
            <span className="font-semibold text-slate-100">
              TanStack Query enabled
            </span>{" "}
            · Charts:{" "}
            <span className="font-semibold text-slate-100">Recharts</span>
          </p>
        </footer>
      </section>
    </main>
  );
}