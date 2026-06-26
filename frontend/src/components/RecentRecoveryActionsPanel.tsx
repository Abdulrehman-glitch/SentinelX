import { Link } from "react-router";
import { Badge, getStatusTone } from "./Badge";
import type { RecoveryAction } from "../types/api";
import { sortRecoveryActionsByNewest } from "../utils/operations";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

type RecentRecoveryActionsPanelProps = {
  recoveryActions: RecoveryAction[];
};

export function RecentRecoveryActionsPanel({
  recoveryActions,
}: RecentRecoveryActionsPanelProps) {
  const recentActions = sortRecoveryActionsByNewest(recoveryActions).slice(0, 5);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Recent Recovery Actions
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Safe self-healing actions logged for traceability.
          </p>
        </div>

        <Link
          to="/recovery-actions"
          className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          View all
        </Link>
      </div>

      {recentActions.length === 0 ? (
        <div className="mt-6 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">
          No recovery actions have been logged yet.
        </div>
      ) : (
        <div className="mt-5 space-y-3">
          {recentActions.map((action, index) => {
            const key =
              action.id ??
              action.recovery_action_id ??
              `${action.device_id}-${action.action_type}-${index}`;

            return (
              <article
                key={key}
                className="rounded-xl border border-slate-200 bg-slate-50 p-4"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-950">
                      {formatLabel(action.action_type)}
                    </p>

                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      {action.details ?? "No details recorded"}
                    </p>

                    <p className="mt-2 text-xs text-slate-400">
                      Device:{" "}
                      {action.device_id
                        ? truncateMiddle(action.device_id, 22)
                        : "Not linked"}{" "}
                      · {formatDate(action.created_at)}
                    </p>
                  </div>

                  <Badge tone={getStatusTone(action.status)}>
                    {action.status}
                  </Badge>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}