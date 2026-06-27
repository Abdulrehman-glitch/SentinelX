import { AlertsTable } from "../components/AlertsTable";
import { ConsoleHeader } from "../components/ConsoleHeader";
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
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Alert Operations"
          title="Signal Review"
          description="Warning and critical conditions generated from monitored telemetry. Alerts can be resolved once reviewed."
        >
          <button
            type="button"
            onClick={() => alertsQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60"
            disabled={alertsQuery.isFetching}
          >
            {alertsQuery.isFetching ? "Refreshing..." : "Refresh alerts"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
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