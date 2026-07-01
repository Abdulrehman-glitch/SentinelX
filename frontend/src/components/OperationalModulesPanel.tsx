import { Link } from "react-router";
import { Badge, getStatusTone } from "./Badge";
import type { AlertRule, AuditLog, Incident } from "../types/api";

type OperationalModulesPanelProps = {
  incidents: Incident[];
  auditLogs: AuditLog[];
  alertRules: AlertRule[];
};

export function OperationalModulesPanel({
  incidents,
  auditLogs,
  alertRules,
}: OperationalModulesPanelProps) {
  const openIncidents = incidents.filter(
    (incident) => incident.status.toLowerCase() !== "resolved",
  );

  const enabledRules = alertRules.filter((rule) => rule.enabled);

  const latestAuditLog = auditLogs[0] ?? null;

  return (
    <section className="mt-8 grid gap-6 xl:grid-cols-3">
      <article className="sx-panel rounded-2xl p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold sx-c-text">Incidents</h2>
            <p className="mt-1 text-sm sx-c-muted">
              Open investigation workload.
            </p>
          </div>

          <Badge tone={getStatusTone(openIncidents.length > 0 ? "open" : "resolved")}>
            {`${openIncidents.length} open`}
          </Badge>
        </div>

        <p className="mt-5 text-4xl font-bold sx-c-text">
          {incidents.length}
        </p>

        <Link
          to="/incidents"
          className="sx-button-secondary mt-5 inline-flex rounded-xl px-4 py-2 text-sm font-semibold"
        >
          Review incidents
        </Link>
      </article>

      <article className="sx-panel rounded-2xl p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold sx-c-text">Alert Rules</h2>
            <p className="mt-1 text-sm sx-c-muted">
              Active telemetry thresholds.
            </p>
          </div>

          <Badge tone={enabledRules.length > 0 ? "green" : "slate"}>
            {`${enabledRules.length} enabled`}
          </Badge>
        </div>

        <p className="mt-5 text-4xl font-bold sx-c-text">
          {alertRules.length}
        </p>

        <Link
          to="/alert-rules"
          className="sx-button-secondary mt-5 inline-flex rounded-xl px-4 py-2 text-sm font-semibold"
        >
          Manage rules
        </Link>
      </article>

      <article className="sx-panel rounded-2xl p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold sx-c-text">Audit Logs</h2>
            <p className="mt-1 text-sm sx-c-muted">
              Latest traceable system action.
            </p>
          </div>

          <Badge tone="blue">{`${auditLogs.length} logs`}</Badge>
        </div>

        <p className="mt-5 text-sm leading-6 sx-c-muted">
          {latestAuditLog?.message ?? "No audit log events recorded yet."}
        </p>

        <Link
          to="/audit-logs"
          className="sx-button-secondary mt-5 inline-flex rounded-xl px-4 py-2 text-sm font-semibold"
        >
          View audit trail
        </Link>
      </article>
    </section>
  );
}