import { Link, useParams } from "react-router";
import { Badge, getSeverityTone, getStatusTone } from "../components/Badge";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { IncidentTimeline } from "../components/IncidentTimeline";
import { PermissionGate } from "../components/PermissionGate";
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
    incidentQuery.error ??
    eventsQuery.error ??
    updateStatusMutation.error ??
    resolveIncidentMutation.error;

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
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6">
          <Link
            to="/incidents"
            className="text-sm font-semibold text-slate-400 transition hover:text-amber-300"
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
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            disabled={incidentQuery.isFetching || eventsQuery.isFetching}
          >
            {incidentQuery.isFetching || eventsQuery.isFetching
              ? "Refreshing..."
              : "Refresh incident"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
            <p className="font-semibold">Incident operation failed.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        {incident && (
          <>
            <section className="grid gap-4 lg:grid-cols-4">
              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold text-slate-400">Severity</p>
                <div className="mt-3">
                  <Badge tone={getSeverityTone(incident.severity)}>
                    {incident.severity}
                  </Badge>
                </div>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold text-slate-400">Status</p>
                <div className="mt-3">
                  <Badge tone={getStatusTone(incident.status)}>
                    {incident.status}
                  </Badge>
                </div>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold text-slate-400">Device</p>
                <p className="mt-3 text-sm font-bold text-slate-50">
                  {incident.device_id
                    ? truncateMiddle(incident.device_id, 24)
                    : "Not linked"}
                </p>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold text-slate-400">Created</p>
                <p className="mt-3 text-sm font-bold text-slate-50">
                  {formatDate(incident.created_at)}
                </p>
              </article>
            </section>

            <section className="sx-panel mt-8 rounded-2xl p-5">
              <h2 className="text-lg font-bold text-slate-50">
                Incident Controls
              </h2>

              <p className="mt-2 text-sm leading-6 text-slate-400">
                {incident.description ?? "No incident description was provided."}
              </p>

              <PermissionGate
                roles={["admin", "engineer"]}
                fallback={
                  <div className="mt-5 rounded-2xl border border-white/[0.056] bg-black/25 p-4 text-sm text-slate-400">
                    Incident controls are read-only for viewers.
                  </div>
                }
              >
                <div className="mt-5 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => updateStatusMutation.mutate("investigating")}
                    disabled={
                      updateStatusMutation.isPending ||
                      incident.status === "investigating" ||
                      incident.status === "resolved"
                    }
                    className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
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
                    className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {resolveIncidentMutation.isPending
                      ? "Resolving..."
                      : "Resolve incident"}
                  </button>
                </div>
              </PermissionGate>

              <p className="mt-4 text-xs text-slate-500">
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