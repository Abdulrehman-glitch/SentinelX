import { AnomalyPredictionsTable } from "../components/AnomalyPredictionsTable";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { PermissionGate } from "../components/PermissionGate";
import { useAnomalyPredictionsQuery } from "../hooks/useAnomalyPredictionsQuery";
import { useRunObservabilityPipelineMutation } from "../hooks/useObservabilityMutations";

export function AnomalyPredictionsPage() {
  const predictionsQuery = useAnomalyPredictionsQuery();
  const runPipelineMutation = useRunObservabilityPipelineMutation();

  const error = predictionsQuery.error ?? runPipelineMutation.error;
  const errorMessage =
    error instanceof Error
      ? error.message
      : error
        ? "Unknown error while loading anomaly predictions."
        : null;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="AI Observability"
          title="Anomaly Predictions"
          description="Shadow-mode, explainable anomaly detection running alongside (never instead of) the deterministic alert rules. Nothing here creates alerts, incidents, or recovery actions automatically."
        >
          <div className="flex items-center gap-2">
            <PermissionGate
              roles={["admin", "owner", "engineer", "platform_admin"]}
              fallback={<span className="text-xs sx-c-text0">Read only</span>}
            >
              <button
                type="button"
                onClick={() => runPipelineMutation.mutate({})}
                disabled={runPipelineMutation.isPending}
                className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              >
                {runPipelineMutation.isPending ? "Running pipeline..." : "Run pipeline"}
              </button>
            </PermissionGate>
            <button
              type="button"
              onClick={() => predictionsQuery.refetch()}
              className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              disabled={predictionsQuery.isFetching}
            >
              {predictionsQuery.isFetching ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm sx-c-danger">
            <p className="font-semibold">Could not load anomaly predictions.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        {runPipelineMutation.isSuccess && runPipelineMutation.data && (
          <div className="mb-6 rounded-2xl border sx-c-border sx-c-surface p-4 text-sm sx-c-muted">
            Pipeline run complete: {runPipelineMutation.data.devices_processed} device(s) processed,{" "}
            {runPipelineMutation.data.windows_built} window(s) built,{" "}
            {runPipelineMutation.data.predictions_created} prediction(s) created.
          </div>
        )}

        <AnomalyPredictionsTable predictions={predictionsQuery.data ?? []} />
      </section>
    </main>
  );
}
