import { ConsoleHeader } from "../components/ConsoleHeader";
import { TopologyMap } from "../components/TopologyMap";
import { useAlertsQuery } from "../hooks/useAlertsQuery";
import { useDevicesQuery } from "../hooks/useDevicesQuery";
import { useIncidentsQuery } from "../hooks/useIncidentsQuery";
import { useRecoveryActionsQuery } from "../hooks/useRecoveryActionsQuery";

export function TopologyPage() {
  const devicesQuery = useDevicesQuery();
  const alertsQuery = useAlertsQuery();
  const incidentsQuery = useIncidentsQuery();
  const recoveryActionsQuery = useRecoveryActionsQuery();

  async function refreshTopology() {
    await Promise.all([
      devicesQuery.refetch(),
      alertsQuery.refetch(),
      incidentsQuery.refetch(),
      recoveryActionsQuery.refetch(),
    ]);
  }

  const isFetching =
    devicesQuery.isFetching ||
    alertsQuery.isFetching ||
    incidentsQuery.isFetching ||
    recoveryActionsQuery.isFetching;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Topology"
          title="System Relationship Map"
          description="Visualise how monitored devices connect to alerts, incidents, and recovery activity across the SentinelX platform."
        >
          <button
            type="button"
            onClick={refreshTopology}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isFetching}
          >
            {isFetching ? "Refreshing..." : "Refresh topology"}
          </button>
        </ConsoleHeader>

        <TopologyMap
          devices={devicesQuery.data ?? []}
          alerts={alertsQuery.data ?? []}
          incidents={incidentsQuery.data ?? []}
          recoveryActions={recoveryActionsQuery.data ?? []}
        />
      </section>
    </main>
  );
}