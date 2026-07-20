import { ConsoleHeader } from "../components/ConsoleHeader";
import { ModelLifecycleCard } from "../components/ModelLifecycleCard";
import { useAnomalyModelsQuery } from "../hooks/useAnomalyModelsQuery";

export function ModelLifecyclePage() {
  const modelsQuery = useAnomalyModelsQuery();

  const errorMessage =
    modelsQuery.error instanceof Error
      ? modelsQuery.error.message
      : modelsQuery.error
        ? "Unknown error while loading registered models."
        : null;

  const models = modelsQuery.data ?? [];

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Model Governance"
          title="Model Lifecycle"
          description="Every model climbs a governed ladder — candidate → shadow → advisory → alert_eligible, or retired — gated by structural checks plus, past shadow, an evaluation report showing enough reviewed predictions and an acceptable false-positive rate."
        >
          <button
            type="button"
            onClick={() => modelsQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            disabled={modelsQuery.isFetching}
          >
            {modelsQuery.isFetching ? "Refreshing..." : "Refresh"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm sx-c-danger">
            <p className="font-semibold">Could not load registered models.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        {models.length === 0 ? (
          <div className="sx-panel rounded-2xl p-8 text-center text-sm sx-c-muted">
            No models registered yet. Train and register a model (see
            <code className="sx-mono mx-1">scripts/train_laptop_isolation_forest.py</code>
            for the reference laptop pipeline) to see it here.
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {models.map((model) => (
              <ModelLifecycleCard key={model.id} model={model} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
