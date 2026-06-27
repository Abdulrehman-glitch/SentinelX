import { AuditLogsTable } from "../components/AuditLogsTable";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";

export function AuditLogsPage() {
  const auditLogsQuery = useAuditLogsQuery();

  const errorMessage =
    auditLogsQuery.error instanceof Error
      ? auditLogsQuery.error.message
      : auditLogsQuery.error
        ? "Unknown error while loading audit logs."
        : null;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Audit Trail"
          title="System Activity Logs"
          description="Traceable records of device registration, alert resolution, incident activity, recovery actions, and rule changes."
        >
          <button
            type="button"
            onClick={() => auditLogsQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            disabled={auditLogsQuery.isFetching}
          >
            {auditLogsQuery.isFetching ? "Refreshing..." : "Refresh logs"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
            <p className="font-semibold">Could not load audit logs.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <AuditLogsTable auditLogs={auditLogsQuery.data ?? []} />
      </section>
    </main>
  );
}