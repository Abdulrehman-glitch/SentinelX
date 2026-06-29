import { ConsoleHeader } from "../components/ConsoleHeader";
import { RecoveryActionsTable } from "../components/RecoveryActionsTable";
import { RecoveryCommandForm } from "../components/RecoveryCommandForm";
import { RecoveryPlaybookTemplates } from "../components/RecoveryPlaybookTemplates";
import { useRecoveryActionsQuery } from "../hooks/useRecoveryActionsQuery";

export function RecoveryCommandPage() {
  const recoveryActionsQuery = useRecoveryActionsQuery();

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Recovery Command"
          title="Safe Self-Healing Control"
          description="Log recovery commands, run safe playbook templates, and review self-healing evidence without executing destructive machine operations."
        >
          <button
            type="button"
            onClick={() => recoveryActionsQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold"
            disabled={recoveryActionsQuery.isFetching}
          >
            {recoveryActionsQuery.isFetching ? "Refreshing..." : "Refresh actions"}
          </button>
        </ConsoleHeader>

        <RecoveryCommandForm />

        <RecoveryPlaybookTemplates />

        <RecoveryActionsTable recoveryActions={recoveryActionsQuery.data ?? []} />
      </section>
    </main>
  );
}