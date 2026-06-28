import { ScrollText } from "lucide-react";
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
    <main className="min-h-screen" style={{ background: "var(--sx-bg)" }}>
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Audit Trail"
          title="System Activity Logs"
          description="Traceable records of device registration, alert resolution, incident activity, recovery actions, and rule changes."
        >
          <button
            type="button"
            onClick={() => auditLogsQuery.refetch()}
            className="sx-button-primary"
            disabled={auditLogsQuery.isFetching}
          >
            {auditLogsQuery.isFetching ? "Refreshing…" : "Refresh logs"}
          </button>
        </ConsoleHeader>

        {/* Info bar */}
        <div
          className="mb-6 flex items-start gap-3 rounded-lg border px-4 py-3 sx-animate-in sx-delay-2"
          style={{ background: "var(--sx-panel)", borderColor: "var(--sx-border)" }}
        >
          <ScrollText
            size={14}
            strokeWidth={1.8}
            className="mt-0.5 shrink-0"
            style={{ color: "var(--sx-muted)" }}
          />
          <p className="text-xs leading-5" style={{ color: "var(--sx-muted)" }}>
            Audit log records are appended automatically on device registration, alert events,
            incident changes, rule updates, and recovery actions. Read-only.
          </p>
          {auditLogsQuery.data && (
            <span
              className="ml-auto shrink-0 rounded border px-2 py-1 text-xs font-semibold tabular-nums"
              style={{
                borderColor: "var(--sx-border-md)",
                background: "var(--sx-bg)",
                color: "var(--sx-text)",
                fontFamily: "var(--font-mono)",
              }}
            >
              {auditLogsQuery.data.length} records
            </span>
          )}
        </div>

        {errorMessage && (
          <div
            className="mb-6 rounded-lg border p-4 text-sm"
            style={{
              borderColor: "rgba(244,63,94,0.24)",
              background: "rgba(244,63,94,0.08)",
              color: "#fb7185",
            }}
          >
            <p className="font-semibold">Could not load audit logs.</p>
            <p className="mt-1" style={{ color: "#fca5a5" }}>{errorMessage}</p>
          </div>
        )}

        <AuditLogsTable auditLogs={auditLogsQuery.data ?? []} />
      </section>
    </main>
  );
}
