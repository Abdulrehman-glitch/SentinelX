import { AlertsTable } from "../components/AlertsTable";
import { DevicesTable } from "../components/DevicesTable";
import { FleetHealthPanel } from "../components/FleetHealthPanel";
import { OperationsSnapshot } from "../components/OperationsSnapshot";
import { RecentAlertsPanel } from "../components/RecentAlertsPanel";
import { RecentRecoveryActionsPanel } from "../components/RecentRecoveryActionsPanel";
import { RecoveryActionsTable } from "../components/RecoveryActionsTable";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { useDashboardData } from "../hooks/useDashboardData";
import { useResolveAlertMutation } from "../hooks/useResolveAlertMutation";
import { API_BASE_URL } from "../lib/api";

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

  const resolveAlertMutation = useResolveAlertMutation();

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

  return (
    <main className="min-h-screen bg-slate-50">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">
              Dashboard
            </p>

            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
              Operations Overview
            </h1>

            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
              Central monitoring view for device availability, telemetry volume,
              unresolved alerts, and logged recovery actions.
            </p>
          </div>

          <div className="flex flex-col items-start gap-2 md:items-end">
            <button
              type="button"
              onClick={refetchAll}
              className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isFetching}
            >
              {isFetching ? "Refreshing..." : "Refresh data"}
            </button>

            <p className="text-xs text-slate-500">
              API: <span className="font-medium">{API_BASE_URL}</span>
            </p>
          </div>
        </header>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
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
                className="h-36 animate-pulse rounded-2xl border border-slate-200 bg-white shadow-sm"
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
              title="Online Devices"
              value={overview?.devices.online ?? 0}
              description="Devices currently reporting online status."
            />

            <StatCard
              title="Offline Devices"
              value={overview?.devices.offline ?? 0}
              description="Registered devices not currently online."
            />

            <StatCard
              title="System Metrics"
              value={overview?.metrics.total ?? 0}
              description="Stored CPU, memory, and disk telemetry records."
            />

            <StatCard
              title="Unresolved Alerts"
              value={overview?.alerts.unresolved ?? 0}
              description="Warning or critical alerts waiting for resolution."
            />

            <StatCard
              title="Recovery Actions"
              value={overview?.recovery_actions.total ?? 0}
              description="Non-destructive recovery actions logged for traceability."
            />
          </section>
        )}

        <OperationsSnapshot
          overview={overview}
          devices={devices}
          alerts={alerts}
          recoveryActions={recoveryActions}
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

        <footer className="mt-8 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
          <p>
            Service:{" "}
            <span className="font-semibold text-slate-900">
              {health?.service ?? "Unknown"}
            </span>
          </p>

          <p className="mt-1">
            Environment:{" "}
            <span className="font-semibold text-slate-900">
              {health?.environment ?? "Unknown"}
            </span>{" "}
            | Version:{" "}
            <span className="font-semibold text-slate-900">
              {health?.version ?? "Unknown"}
            </span>
          </p>

          <p className="mt-1">
            Cache:{" "}
            <span className="font-semibold text-slate-900">
              TanStack Query enabled
            </span>
          </p>
        </footer>
      </section>
    </main>
  );
}