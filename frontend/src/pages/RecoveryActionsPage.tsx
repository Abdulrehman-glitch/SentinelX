import { ConsoleHeader } from "../components/ConsoleHeader";
import { RecoveryActionsTable } from "../components/RecoveryActionsTable";
import { useRecoveryActionsQuery } from "../hooks/useRecoveryActionsQuery";

export function RecoveryActionsPage() {
  const recoveryActionsQuery = useRecoveryActionsQuery();

  const errorMessage =
    recoveryActionsQuery.error instanceof Error
      ? recoveryActionsQuery.error.message
      : recoveryActionsQuery.error
        ? "Unknown error while loading recovery actions."
        : null;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Recovery Ledger"
          title="Self-Healing Actions"
          description="Logged non-destructive recovery actions used to demonstrate safe automated recovery and traceability."
        >
          <button
            type="button"
            onClick={() => recoveryActionsQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60"
            disabled={recoveryActionsQuery.isFetching}
          >
            {recoveryActionsQuery.isFetching ? "Refreshing..." : "Refresh actions"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
            <p className="font-semibold">Could not load recovery actions.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <RecoveryActionsTable recoveryActions={recoveryActionsQuery.data ?? []} />

        <p className="mt-4 text-xs text-slate-500">
          Cache: TanStack Query enabled
        </p>
      </section>
    </main>
  );
}