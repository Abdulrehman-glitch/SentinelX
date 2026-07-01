import { ShieldAlert } from "lucide-react";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { SecurityLogsTable } from "../components/SecurityLogsTable";
import { useSecurityLogsQuery } from "../hooks/useSecurityLogsQuery";

export function SecurityLogsPage() {
  const securityLogsQuery = useSecurityLogsQuery();

  const errorMessage =
    securityLogsQuery.error instanceof Error
      ? securityLogsQuery.error.message
      : securityLogsQuery.error
        ? "Unknown error while loading security logs."
        : null;

  return (
    <main className="min-h-screen" style={{ background: "var(--sx-bg)" }}>
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Security Centre"
          title="Backend Security Logs"
          description="Restricted forensic log for authentication, authorization, device-token, suspicious-request, and rate-limit events."
        >
          <button
            type="button"
            onClick={() => securityLogsQuery.refetch()}
            className="sx-button-primary"
            disabled={securityLogsQuery.isFetching}
          >
            {securityLogsQuery.isFetching ? "Refreshing…" : "Refresh security logs"}
          </button>
        </ConsoleHeader>

        <div
          className="mb-6 flex items-start gap-3 rounded-lg border px-4 py-3 sx-animate-in sx-delay-2"
          style={{ background: "var(--sx-panel)", borderColor: "var(--sx-border)" }}
        >
          <ShieldAlert
            size={14}
            strokeWidth={1.8}
            className="mt-0.5 shrink-0"
            style={{ color: "var(--sx-muted)" }}
          />
          <p className="text-xs leading-5" style={{ color: "var(--sx-muted)" }}>
            Security logs are separate from business audit logs and should only be visible to tenant admins,
            owners, and platform admins. Sensitive secrets such as plaintext passwords and raw tokens are not shown.
          </p>
          {securityLogsQuery.data && (
            <span
              className="ml-auto shrink-0 rounded border px-2 py-1 text-xs font-semibold tabular-nums"
              style={{
                borderColor: "var(--sx-border-md)",
                background: "var(--sx-bg)",
                color: "var(--sx-text)",
                fontFamily: "var(--font-mono)",
              }}
            >
              {securityLogsQuery.data.length} records
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
            <p className="font-semibold">Could not load security logs.</p>
            <p className="mt-1" style={{ color: "#fca5a5" }}>{errorMessage}</p>
          </div>
        )}

        <SecurityLogsTable securityLogs={securityLogsQuery.data ?? []} />
      </section>
    </main>
  );
}
