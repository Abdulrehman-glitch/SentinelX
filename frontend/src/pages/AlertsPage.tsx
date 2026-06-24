import { AlertsTable } from "../components/AlertsTable";
import { useSentinelXData } from "../hooks/useSentinelXData";

export function AlertsPage() {
  const {
    alerts,
    isLoading,
    resolvingAlertId,
    errorMessage,
    lastUpdated,
    loadDashboardData,
    resolveAlert,
  } = useSentinelXData();

  return (
    <main className="min-h-screen bg-slate-50">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">
              Alerts
            </p>

            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
              Alert Management
            </h1>

            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              Warning and critical conditions generated from monitored system
              metrics. Alerts can be resolved once reviewed.
            </p>
          </div>

          <button
            type="button"
            onClick={loadDashboardData}
            className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isLoading}
          >
            {isLoading ? "Refreshing..." : "Refresh alerts"}
          </button>
        </header>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            <p className="font-semibold">Could not load alerts.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <AlertsTable
          alerts={alerts}
          resolvingAlertId={resolvingAlertId}
          onResolveAlert={resolveAlert}
        />

        <p className="mt-4 text-xs text-slate-500">
          Last updated: {lastUpdated ? lastUpdated.toLocaleString() : "Not loaded yet"}
        </p>
      </section>
    </main>
  );
}