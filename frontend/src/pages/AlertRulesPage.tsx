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
    <main className="min-h-screen" style={{ background: "var(--sx-bg)" }}>
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Rule Engine"
          title="Alert Rules"
          description="Configure threshold rules that convert telemetry conditions into warning and critical alerts."
        >
          <button
            type="button"
            onClick={() => alertRulesQuery.refetch()}
            className="sx-button-primary"
            disabled={alertRulesQuery.isFetching}
          >
            {alertRulesQuery.isFetching ? "Refreshing..." : "Refresh rules"}
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
            <p className="font-semibold">Could not load alert rules.</p>
            <p className="mt-1" style={{ color: "var(--sx-red)" }}>{errorMessage}</p>
          </div>
        )}

        <CreateAlertRuleForm />
        <AlertRulesTable alertRules={alertRulesQuery.data ?? []} />
      </section>
    </main>
  );
}