import { RecoveryCommandsTable } from "../components/RecoveryCommandsTable";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { useRecoveryCommandsQuery } from "../hooks/useRecoveryCommandsQuery";

export function RecoveryCommandsPage() {
  const commandsQuery = useRecoveryCommandsQuery();

  const errorMessage =
    commandsQuery.error instanceof Error
      ? commandsQuery.error.message
      : commandsQuery.error
        ? "Unknown error while loading recovery commands."
        : null;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Safe Recovery Orchestration"
          title="Recovery Command Centre"
          description="Signed, verifiable, allowlisted commands connecting the backend to desktop and Android agents. AI may recommend a command; only the deterministic policy engine — never the model — decides whether it may run."
        >
          <button
            type="button"
            onClick={() => commandsQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            disabled={commandsQuery.isFetching}
          >
            {commandsQuery.isFetching ? "Refreshing..." : "Refresh"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm sx-c-danger">
            <p className="font-semibold">Could not load recovery commands.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <RecoveryCommandsTable commands={commandsQuery.data ?? []} />
      </section>
    </main>
  );
}
