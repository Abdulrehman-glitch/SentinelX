import { AlertsTable } from "../components/AlertsTable";
import { useAlertsQuery } from "../hooks/useAlertsQuery";
import { useResolveAlertMutation } from "../hooks/useResolveAlertMutation";

export function AlertsPage() {
  const alertsQuery = useAlertsQuery();
  const resolveAlertMutation = useResolveAlertMutation();

  const queryErrorMessage =
    alertsQuery.error instanceof Error
      ? alertsQuery.error.message
      : alertsQuery.error
        ? "Unknown error while loading alerts."
        : null;

  const mutationErrorMessage =
    resolveAlertMutation.error instanceof Error
      ? resolveAlertMutation.error.message
      : resolveAlertMutation.error
        ? "Unknown error while resolving alert."
        : null;

  const errorMessage = queryErrorMessage ?? mutationErrorMessage;

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
            onClick={() => alertsQuery.refetch()}
            className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={alertsQuery.isFetching}
          >
            {alertsQuery.isFetching ? "Refreshing..." : "Refresh alerts"}
          </button>
        </header>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            <p className="font-semibold">Alert operation failed.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <AlertsTable
          alerts={alertsQuery.data ?? []}
          resolvingAlertId={
            typeof resolveAlertMutation.variables === "string"
              ? resolveAlertMutation.variables
              : null
          }
          onResolveAlert={resolveAlertMutation.mutate}
        />

        <p className="mt-4 text-xs text-slate-500">
          Cache: TanStack Query enabled
        </p>
      </section>
    </main>
  );
}