import { Badge } from "./Badge";
import type { RecoveryCommandEvent } from "../types/api";
import { formatDate, formatLabel } from "../utils/format";

type RecoveryCommandTimelineProps = {
  events: RecoveryCommandEvent[];
};

function actorTone(actorType: string) {
  if (actorType === "agent") return "green" as const;
  if (actorType === "policy") return "violet" as const;
  if (actorType === "system") return "blue" as const;
  return "slate" as const;
}

export function RecoveryCommandTimeline({ events }: RecoveryCommandTimelineProps) {
  const sortedEvents = [...events].sort((a, b) => {
    const aDate = new Date(a.created_at).getTime();
    const bDate = new Date(b.created_at).getTime();
    return (Number.isNaN(bDate) ? 0 : bDate) - (Number.isNaN(aDate) ? 0 : aDate);
  });

  return (
    <section className="sx-panel mt-8 rounded-2xl p-5">
      <h2 className="text-lg font-bold sx-c-text">Command Event Timeline</h2>
      <p className="mt-1 text-sm sx-c-muted">
        Append-only history — every state transition (proposal, approval, dispatch, execution,
        verification) is recorded here and cannot be edited or deleted.
      </p>

      {sortedEvents.length === 0 ? (
        <div className="mt-6 rounded-xl border sx-c-border sx-c-surface p-6 text-sm sx-c-muted">
          No events recorded yet.
        </div>
      ) : (
        <div className="mt-6 space-y-4">
          {sortedEvents.map((event) => (
            <article key={event.id} className="rounded-2xl border sx-c-border sx-c-surface p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-bold sx-c-text">
                    {event.previous_status ? (
                      <>
                        {formatLabel(event.previous_status)} → {formatLabel(event.new_status ?? "")}
                      </>
                    ) : (
                      formatLabel(event.event_type)
                    )}
                  </p>

                  {event.message && <p className="mt-2 text-sm leading-6 sx-c-muted">{event.message}</p>}

                  <p className="mt-3 text-xs sx-c-text0">
                    {formatLabel(event.actor_type)}
                    {event.actor_id ? ` · ${event.actor_id}` : ""} · {formatDate(event.created_at)}
                  </p>
                </div>

                <Badge tone={actorTone(event.actor_type)}>{event.actor_type}</Badge>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
