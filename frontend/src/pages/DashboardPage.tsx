import { useMemo } from "react";
import { CommandState } from "../components/CommandState";
import { DashStatusBar } from "../components/DashStatusBar";
import { FleetConstellation } from "../components/FleetConstellation";
import { LiveEventStream } from "../components/LiveEventStream";
import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";
import { useDashboardData } from "../hooks/useDashboardData";
import { useIncidentsQuery } from "../hooks/useIncidentsQuery";
import { buildEventStream } from "../utils/dashboard";
import { getOperationalPosture } from "../utils/operations";

export function DashboardPage() {
  const {
    overview,
    health,
    devices,
    alerts,
    recoveryActions,
    isLoading,
    isFetching,
    refetchAll,
  } = useDashboardData();

  const incidentsQuery = useIncidentsQuery();
  const auditLogsQuery = useAuditLogsQuery();

  const posture = getOperationalPosture(overview, devices, alerts);

  const streamEvents = useMemo(
    () => buildEventStream(alerts, recoveryActions, auditLogsQuery.data ?? [], 50),
    [alerts, recoveryActions, auditLogsQuery.data],
  );

  async function handleRefresh() {
    await Promise.all([
      refetchAll(),
      incidentsQuery.refetch(),
      auditLogsQuery.refetch(),
    ]);
  }

  const dashIsFetching =
    isFetching || incidentsQuery.isFetching || auditLogsQuery.isFetching;

  return (
    <div
      className="dash-console flex flex-col"
      style={{ minHeight: "100dvh" }}
    >
      {/* Fixed-height top status bar */}
      <DashStatusBar
        health={health}
        overview={overview}
        posture={posture}
        isFetching={dashIsFetching}
        onRefresh={handleRefresh}
      />

      {/* Console grid: stacked on mobile, three independently-scrollable columns on lg+ */}
      <div
        className="dc-console-grid flex flex-1 flex-col lg:flex-row"
        aria-label="Operations console"
      >
        {/* Left: Fleet Monitor */}
        <div
          className="dc-console-col flex-1 border-b border-[rgba(200,16,46,0.09)] lg:border-b-0 lg:border-r lg:overflow-y-auto"
          style={{ background: "var(--sx-panel)" }}
        >
          <FleetConstellation
            devices={devices}
            alerts={alerts}
            isLoading={isLoading}
          />
        </div>

        {/* Centre: Event Stream */}
        <div
          className="dc-console-col border-b border-[rgba(200,16,46,0.09)] lg:w-[370px] lg:shrink-0 lg:border-b-0 lg:border-r lg:overflow-y-auto"
          style={{ background: "var(--sx-panel-2)" }}
        >
          <LiveEventStream events={streamEvents} isLoading={isLoading} />
        </div>

        {/* Right: Command State */}
        <div
          className="dc-console-col lg:w-[272px] lg:shrink-0 lg:overflow-y-auto"
          style={{ background: "var(--sx-panel)" }}
        >
          <CommandState
            overview={overview}
            devices={devices}
            alerts={alerts}
            incidents={incidentsQuery.data ?? []}
            posture={posture}
          />
        </div>
      </div>
    </div>
  );
}
