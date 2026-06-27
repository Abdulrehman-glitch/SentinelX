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

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Incident Response"
          title="Operational Incidents"
          description="Create, investigate, update, and resolve incidents linked to alerts, devices, and recovery activity."
        >
          <button
            type="button"
            onClick={() => incidentsQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            disabled={incidentsQuery.isFetching}
          >
            {incidentsQuery.isFetching ? "Refreshing..." : "Refresh incidents"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
            <p className="font-semibold">Could not load incidents.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <CreateIncidentForm />
        <IncidentsTable incidents={incidentsQuery.data ?? []} />
      </section>
    </main>
  );
}