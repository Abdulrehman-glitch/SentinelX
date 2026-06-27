import { AlertRulesTable } from "../components/AlertRulesTable";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { CreateAlertRuleForm } from "../components/CreateAlertRuleForm";
import { useAlertRulesQuery } from "../hooks/useAlertRulesQuery";

export function AlertRulesPage() {
  const alertRulesQuery = useAlertRulesQuery();

  const errorMessage =
    alertRulesQuery.error instanceof Error
      ? alertRulesQuery.error.message
      : alertRulesQuery.error
        ? "Unknown error while loading alert rules."
        : null;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Rule Engine"
          title="Alert Rules"
          description="Configure threshold rules that convert telemetry conditions into warning and critical alerts."
        >
          <button
            type="button"
            onClick={() => alertRulesQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            disabled={alertRulesQuery.isFetching}
          >
            {alertRulesQuery.isFetching ? "Refreshing..." : "Refresh rules"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
            <p className="font-semibold">Could not load alert rules.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <CreateAlertRuleForm />
        <AlertRulesTable alertRules={alertRulesQuery.data ?? []} />
      </section>
    </main>
  );
}