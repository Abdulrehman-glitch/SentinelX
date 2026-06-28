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
    <section className="sx-panel rounded-2xl p-5 sx-animate-in sx-delay-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">
            Recent Recovery Actions
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            Safe self-healing actions logged for traceability.
          </p>
        </div>

        <Link
          to="/recovery-actions"
          className="sx-button-secondary rounded-lg px-3 py-2 text-xs font-semibold"
        >
          View all
        </Link>
      </div>

      {recentActions.length === 0 ? (
        <div className="mt-6 rounded-xl border border-slate-700/50 bg-slate-900/50 p-4 text-sm text-slate-400">
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
                className="rounded-xl border border-slate-700/40 bg-slate-900/50 p-4 transition hover:border-slate-600/60 hover:bg-slate-800/50"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-100">
                      {formatLabel(action.action_type)}
                    </p>

                    <p className="mt-1 text-sm leading-6 text-slate-400">
                      {action.details ?? "No details recorded"}
                    </p>

                    <p className="mt-2 text-xs text-slate-500">
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
