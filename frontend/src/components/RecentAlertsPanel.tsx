import { Link } from "react-router";
import { Badge, getSeverityTone, getStatusTone } from "./Badge";
import type { Alert } from "../types/api";
import {
  getAlertId,
  getAlertType,
  isAlertResolved,
  sortAlertsForOperations,
} from "../utils/operations";
import { formatDate, formatLabel } from "../utils/format";

type RecentAlertsPanelProps = {
  alerts: Alert[];
  resolvingAlertId: string | null;
  onResolveAlert: (alertId: string) => void;
};

export function RecentAlertsPanel({
  alerts,
  resolvingAlertId,
  onResolveAlert,
}: RecentAlertsPanelProps) {
  const recentAlerts = sortAlertsForOperations(alerts).slice(0, 5);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Priority Alerts
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Most urgent unresolved and recent alert events.
          </p>
        </div>

        <Link
          to="/alerts"
          className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          View all
        </Link>
      </div>

      {recentAlerts.length === 0 ? (
        <div className="mt-6 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">
          No alerts have been generated yet.
        </div>
      ) : (
        <div className="mt-5 space-y-3">
          {recentAlerts.map((alert, index) => {
            const alertId = getAlertId(alert);
            const resolved = isAlertResolved(alert);
            const status = resolved ? "resolved" : "unresolved";

            return (
              <article
                key={alertId || `${alert.message}-${index}`}
                className="rounded-xl border border-slate-200 bg-slate-50 p-4"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="flex flex-wrap gap-2">
                      <Badge tone={getSeverityTone(alert.severity)}>
                        {alert.severity}
                      </Badge>

                      <Badge tone={getStatusTone(status)}>{status}</Badge>
                    </div>

                    <p className="mt-3 text-sm font-semibold text-slate-950">
                      {formatLabel(getAlertType(alert))}
                    </p>

                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      {alert.message}
                    </p>

                    <p className="mt-2 text-xs text-slate-400">
                      {formatDate(alert.created_at)}
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={() => onResolveAlert(alertId)}
                    disabled={resolved || !alertId || resolvingAlertId === alertId}
                    className="rounded-lg bg-slate-950 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    {resolvingAlertId === alertId
                      ? "Resolving..."
                      : resolved
                        ? "Resolved"
                        : "Resolve"}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}