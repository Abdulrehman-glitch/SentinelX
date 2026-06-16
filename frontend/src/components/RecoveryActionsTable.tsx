import type { RecoveryAction } from "../types/api";

type RecoveryActionsTableProps = {
  recoveryActions: RecoveryAction[];
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

function getRecoveryActionId(action: RecoveryAction) {
  return action.id ?? action.recovery_action_id ?? "";
}

function formatActionType(actionType: string) {
  return actionType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function getStatusClasses(status: string) {
  const normalisedStatus = status.toLowerCase();

  if (
    normalisedStatus === "completed" ||
    normalisedStatus === "success" ||
    normalisedStatus === "logged"
  ) {
    return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200";
  }

  if (
    normalisedStatus === "pending" ||
    normalisedStatus === "queued" ||
    normalisedStatus === "running"
  ) {
    return "bg-amber-50 text-amber-700 ring-1 ring-amber-200";
  }

  if (normalisedStatus === "failed" || normalisedStatus === "error") {
    return "bg-rose-50 text-rose-700 ring-1 ring-rose-200";
  }

  return "bg-slate-100 text-slate-700 ring-1 ring-slate-200";
}

export function RecoveryActionsTable({
  recoveryActions,
}: RecoveryActionsTableProps) {
  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-lg font-semibold text-slate-950">
          Recovery Actions
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Non-destructive self-healing actions logged by SentinelX for safety,
          traceability, and project evidence.
        </p>
      </div>

      {recoveryActions.length === 0 ? (
        <div className="px-5 py-8 text-sm text-slate-500">
          No recovery actions have been logged yet. Trigger or manually log a
          recovery action through the backend API to verify this table.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Action Type
                </th>

                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Status
                </th>

                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Device ID
                </th>

                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Details
                </th>

                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Created
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100 bg-white">
              {recoveryActions.map((action, index) => {
                const actionId = getRecoveryActionId(action);
                const key =
                  actionId ||
                  `${action.device_id}-${action.action_type}-${index}`;

                return (
                  <tr key={key} className="hover:bg-slate-50">
                    <td className="whitespace-nowrap px-5 py-4 text-sm font-medium text-slate-950">
                      {formatActionType(action.action_type)}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-sm">
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${getStatusClasses(
                          action.status,
                        )}`}
                      >
                        {action.status}
                      </span>
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-sm text-slate-600">
                      {action.device_id ?? "Not linked"}
                    </td>

                    <td className="max-w-xl px-5 py-4 text-sm text-slate-600">
                      {action.details ?? "No details recorded"}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-sm text-slate-600">
                      {formatDate(action.created_at)}
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