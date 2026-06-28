import { ConsoleHeader } from "../components/ConsoleHeader";
import { CreateIncidentForm } from "../components/CreateIncidentForm";
import { IncidentsTable } from "../components/IncidentsTable";
import { useIncidentsQuery } from "../hooks/useIncidentsQuery";

export function IncidentsPage() {
  const incidentsQuery = useIncidentsQuery();

  const errorMessage =
    incidentsQuery.error instanceof Error
      ? incidentsQuery.error.message
      : incidentsQuery.error
        ? "Unknown error while loading incidents."
        : null;

  const incidents = incidentsQuery.data ?? [];
  const open      = incidents.filter((i) => i.status.toLowerCase() !== "resolved").length;
  const resolved  = incidents.length - open;

  return (
    <main className="min-h-screen" style={{ background: "var(--sx-bg)" }}>
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Incident Response"
          title="Operational Incidents"
          description="Create, investigate, update, and resolve incidents linked to alerts, devices, and recovery activity."
        >
          <button
            type="button"
            onClick={() => incidentsQuery.refetch()}
            className="sx-button-primary"
            disabled={incidentsQuery.isFetching}
          >
            {incidentsQuery.isFetching ? "Refreshing…" : "Refresh incidents"}
          </button>
        </ConsoleHeader>

        {incidents.length > 0 && (
          <div className="mb-6 grid gap-3 sm:grid-cols-3 sx-animate-in sx-delay-2">
            <SummaryCard label="Total incidents" value={incidents.length} />
            <SummaryCard label="Open"     value={open}     dotColor="#f43f5e" valueColor="#fb7185" />
            <SummaryCard label="Resolved" value={resolved} dotColor="#22c55e" valueColor="#4ade80" />
          </div>
        )}

        {errorMessage && <ErrorBanner message={errorMessage} />}

        <CreateIncidentForm />
        <IncidentsTable incidents={incidents} />
      </section>
    </main>
  );
}

function SummaryCard({
  label,
  value,
  dotColor,
  valueColor,
}: {
  label: string;
  value: number;
  dotColor?: string;
  valueColor?: string;
}) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border px-4 py-3"
      style={{ background: "var(--sx-panel)", borderColor: "var(--sx-border)" }}
    >
      {dotColor ? (
        <span className="sx-live-dot shrink-0" style={{ color: dotColor }} />
      ) : (
        <span
          className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
          style={{ background: "var(--sx-muted)" }}
        />
      )}
      <div>
        <p className="text-xs" style={{ color: "var(--sx-muted)" }}>{label}</p>
        <p className="text-sm font-bold" style={{ color: valueColor ?? "var(--sx-text)" }}>
          {value}
        </p>
      </div>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      className="mb-6 rounded-lg border p-4 text-sm"
      style={{
        borderColor: "rgba(244,63,94,0.24)",
        background: "rgba(244,63,94,0.08)",
        color: "#fb7185",
      }}
    >
      <p className="font-semibold">Could not load incidents.</p>
      <p className="mt-1" style={{ color: "#fca5a5" }}>{message}</p>
    </div>
  );
}
