import { HybridDecisionsTable } from "../components/HybridDecisionsTable";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { PermissionGate } from "../components/PermissionGate";
import { useHybridDecisionsQuery } from "../hooks/useHybridDecisionsQuery";
import { useRunHybridDetectionMutation } from "../hooks/useHybridDetectionMutations";

export function HybridDecisionsPage() {
  const decisionsQuery = useHybridDecisionsQuery();
  const runHybridMutation = useRunHybridDetectionMutation();

  const error = decisionsQuery.error ?? runHybridMutation.error;
  const errorMessage =
    error instanceof Error
      ? error.message
      : error
        ? "Unknown error while loading hybrid decisions."
        : null;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Hybrid Detection"
          title="Hybrid Decisions"
          description="Deterministic alert rules stay authoritative — AI evidence from the statistical baseline and IsolationForest can only raise severity, never lower it below a fired rule's. Nothing here creates alerts or incidents; it folds what the rest of the pipeline already produced into one explainable decision."
        >
          <div className="flex items-center gap-2">
            <PermissionGate
              roles={["admin", "owner", "engineer", "platform_admin"]}
              fallback={<span className="text-xs sx-c-text0">Read only</span>}
            >
              <button
                type="button"
                onClick={() => runHybridMutation.mutate({})}
                disabled={runHybridMutation.isPending}
                className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              >
                {runHybridMutation.isPending ? "Running hybrid pipeline..." : "Run hybrid pipeline"}
              </button>
            </PermissionGate>
            <button
              type="button"
              onClick={() => decisionsQuery.refetch()}
              className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              disabled={decisionsQuery.isFetching}
            >
              {decisionsQuery.isFetching ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm sx-c-danger">
            <p className="font-semibold">Could not load hybrid decisions.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        {runHybridMutation.isSuccess && runHybridMutation.data && (
          <div className="mb-6 rounded-2xl border sx-c-border sx-c-surface p-4 text-sm sx-c-muted">
            Hybrid pipeline run complete: {runHybridMutation.data.devices_processed} device(s) processed,{" "}
            {runHybridMutation.data.windows_built} window(s) built,{" "}
            {runHybridMutation.data.decisions_created} decision(s) created.
          </div>
        )}

        <HybridDecisionsTable decisions={decisionsQuery.data ?? []} />
      </section>
    </main>
  );
}
