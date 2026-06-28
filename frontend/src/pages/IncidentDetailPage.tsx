import { Link, useParams } from "react-router";
import { Badge, getSeverityTone, getStatusTone } from "../components/Badge";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { IncidentTimeline } from "../components/IncidentTimeline";
import { useIncidentEventsQuery } from "../hooks/useIncidentEventsQuery";
import { useIncidentQuery } from "../hooks/useIncidentQuery";
import {
  useResolveIncidentMutation,
  useUpdateIncidentStatusMutation,
} from "../hooks/useOperationalMutations";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

export function IncidentDetailPage() {
  const params = useParams();
  const incidentId = params.incidentId ?? "";

  const incidentQuery = useIncidentQuery(incidentId);
  const eventsQuery = useIncidentEventsQuery(incidentId);

  const updateStatusMutation = useUpdateIncidentStatusMutation(incidentId);
  const resolveIncidentMutation = useResolveIncidentMutation(incidentId);

  const incident = incidentQuery.data ?? null;

  const error =
    incidentQuery.error ?? eventsQuery.error ?? updateStatusMutation.error ?? resolveIncidentMutation.error;

  const errorMessage =
    error instanceof Error
      ? error.message
      : error
        ? "Unknown error while loading incident."
        : null;

  async function refreshIncident() {
    await Promise.all([incidentQuery.refetch(), eventsQuery.refetch()]);
  }

  return (
    <main className="min-h-screen" style={{ background: "var(--sx-bg)" }}>
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6">
          <Link
            to="/incidents"
            className="text-sm font-medium transition-colors hover:text-amber-400"
            style={{ color: "var(--sx-muted)" }}
          >
            ← Back to incidents
          </Link>
        </div>

        <ConsoleHeader
          eyebrow="Incident Detail"
          title={incident?.title ?? "Loading incident..."}
          description="Timeline-driven investigation view for operational incidents."
        >
          <button
            type="button"
            onClick={refreshIncident}
            className="sx-button-primary"
            disabled={incidentQuery.isFetching || eventsQuery.isFetching}
          >
            {incidentQuery.isFetching || eventsQuery.isFetching
              ? "Refreshing..."
              : "Refresh incident"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div
            className="mb-6 rounded-lg border p-4 text-sm"
            style={{ borderColor: "rgba(244,63,94,0.24)", background: "rgba(244,63,94,0.08)", color: "#fb7185" }}
          >
            <p className="font-semibold">Incident operation failed.</p>
            <p className="mt-1" style={{ color: "#fca5a5" }}>{errorMessage}</p>
          </div>
        )}

        {incident && (
          <>
            <section className="grid gap-4 lg:grid-cols-4 sx-animate-in sx-delay-2">
              <article className="sx-panel p-5">
                <p className="text-xs font-medium" style={{ color: "var(--sx-muted)" }}>Severity</p>
                <div className="mt-3">
                  <Badge tone={getSeverityTone(incident.severity)}>
                    {incident.severity}
                  </Badge>
                </div>
              </article>

              <article className="sx-panel p-5">
                <p className="text-xs font-medium" style={{ color: "var(--sx-muted)" }}>Status</p>
                <div className="mt-3">
                  <Badge tone={getStatusTone(incident.status)}>
                    {incident.status}
                  </Badge>
                </div>
              </article>

              <article className="sx-panel p-5">
                <p className="text-xs font-medium" style={{ color: "var(--sx-muted)" }}>Device</p>
                <p className="mt-2 text-sm font-bold" style={{ color: "var(--sx-text)" }}>
                  {incident.device_id
                    ? truncateMiddle(incident.device_id, 24)
                    : "Not linked"}
                </p>
              </article>

              <article className="sx-panel p-5">
                <p className="text-xs font-medium" style={{ color: "var(--sx-muted)" }}>Created</p>
                <p className="mt-2 text-sm font-bold" style={{ color: "var(--sx-text)" }}>
                  {formatDate(incident.created_at)}
                </p>
              </article>
            </section>

            <section className="sx-panel mt-8 p-5">
              <h2 className="text-base font-semibold" style={{ color: "var(--sx-text)" }}>Incident Controls</h2>

              <p className="mt-2 text-sm leading-6" style={{ color: "var(--sx-muted)" }}>
                {incident.description ?? "No incident description was provided."}
              </p>

              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => updateStatusMutation.mutate("investigating")}
                  disabled={
                    updateStatusMutation.isPending ||
                    incident.status === "investigating" ||
                    incident.status === "resolved"
                  }
                  className="sx-button-secondary disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Mark investigating
                </button>

                <button
                  type="button"
                  onClick={() => resolveIncidentMutation.mutate()}
                  disabled={
                    resolveIncidentMutation.isPending ||
                    incident.status === "resolved"
                  }
                  className="sx-button-primary disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {resolveIncidentMutation.isPending ? "Resolving..." : "Resolve incident"}
                </button>
              </div>

              <p className="mt-4 text-xs" style={{ color: "var(--sx-dim)" }}>
                Source: {formatLabel(incident.source)} · Assigned to:{" "}
                {incident.assigned_to ?? "Unassigned"}
              </p>
            </section>

            <IncidentTimeline
              incident={incident}
              events={eventsQuery.data ?? []}
            />
          </>
        )}
      </section>
    </main>
  );
}