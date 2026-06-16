import type { Alert } from "../types/api";

type AlertsTableProps = {
  alerts: Alert[];
  resolvingAlertId: string | null;
  onResolveAlert: (alertId: string) => void;
};

function formatDate(value?: string | null) {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function getAlertId(alert: Alert) {
  return alert.id ?? alert.alert_id ?? "";
}

function getAlertType(alert: Alert) {
  return alert.alert_type ?? alert.metric_type ?? "system";
}

function isAlertResolved(alert: Alert) {
  return alert.resolved ?? alert.is_resolved ?? false;
}

function getSeverityClasses(severity: string) {
  const normalisedSeverity = severity.toLowerCase();

  if (normalisedSeverity === "critical") {
    return "bg-rose-50 text-rose-700 ring-1 ring-rose-200";
  }

  if (normalisedSeverity === "warning") {
    return "bg-amber-50 text-amber-700 ring-1 ring-amber-200";
  }

  return "bg-slate-100 text-slate-700 ring-1 ring-slate-200";
}

export function AlertsTable({
  alerts,
  resolvingAlertId,
  onResolveAlert,
}: AlertsTableProps) {
  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-lg font-semibold text-slate-950">Alerts</h2>

        <p className="mt-1 text-sm text-slate-500">
          Rule-based warning and critical alerts generated from system metrics.
        </p>
      </div>

      {alerts.length === 0 ? (
        <div className="px-5 py-8 text-sm text-slate-500">
          No alerts have been generated yet. Send a high CPU, memory, or disk
          metric to trigger alert creation.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Type
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Severity
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Message
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Status
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Created
                </th>
                <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Action
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100 bg-white">
              {alerts.map((alert, index) => {
                const alertId = getAlertId(alert);
                const resolved = isAlertResolved(alert);
                const key = alertId || `${alert.message}-${index}`;

                return (
                  <tr key={key} className="hover:bg-slate-50">
                    <td className="whitespace-nowrap px-5 py-4 text-sm font-medium text-slate-950">
                      {getAlertType(alert)}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-sm">
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${getSeverityClasses(
                          alert.severity,
                        )}`}
                      >
                        {alert.severity}
                      </span>
                    </td>

                    <td className="max-w-xl px-5 py-4 text-sm text-slate-600">
                      {alert.message}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-sm">
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${
                          resolved
                            ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                            : "bg-rose-50 text-rose-700 ring-1 ring-rose-200"
                        }`}
                      >
                        {resolved ? "resolved" : "unresolved"}
                      </span>
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-sm text-slate-600">
                      {formatDate(alert.created_at)}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-right text-sm">
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
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}