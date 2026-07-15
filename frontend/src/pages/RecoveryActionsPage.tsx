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
    <main className="min-h-screen" style={{ background: "var(--sx-bg)" }}>
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Recovery Ledger"
          title="Self-Healing Actions"
          description="Logged non-destructive recovery actions used to demonstrate safe automated recovery and traceability."
        >
          <button
            type="button"
            onClick={() => recoveryActionsQuery.refetch()}
            className="sx-button-primary"
            disabled={recoveryActionsQuery.isFetching}
          >
            {recoveryActionsQuery.isFetching ? "Refreshing..." : "Refresh actions"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div
            className="mb-6 rounded-lg border p-4 text-sm"
            style={{
              borderColor: "rgba(244,63,94,0.24)",
              background: "rgba(244,63,94,0.08)",
              color: "var(--sx-red)",
            }}
          >
            <p className="font-semibold">Could not load recovery actions.</p>
            <p className="mt-1" style={{ color: "var(--sx-red)" }}>{errorMessage}</p>
          </div>
        )}

        <RecoveryActionsTable recoveryActions={recoveryActionsQuery.data ?? []} />
      </section>
    </main>
  );
}