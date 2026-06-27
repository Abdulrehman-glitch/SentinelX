import { useState } from "react";
import { Badge, getStatusTone } from "./Badge";
import type { Incident, IncidentEvent } from "../types/api";
import { useCreateIncidentEventMutation } from "../hooks/useOperationalMutations";
import { formatDate, formatLabel } from "../utils/format";

type IncidentTimelineProps = {
  incident: Incident;
  events: IncidentEvent[];
};

export function IncidentTimeline({ incident, events }: IncidentTimelineProps) {
  const [message, setMessage] = useState("");
  const createEventMutation = useCreateIncidentEventMutation(incident.id);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedMessage = message.trim();

    if (!trimmedMessage) {
      return;
    }

    await createEventMutation.mutateAsync({
      event_type: "comment_added",
      message: trimmedMessage,
      actor_type: "user",
      actor_id: "Engineer",
      metadata: {
        note_type: "manual_review",
      },
    });

    setMessage("");
  }

  const sortedEvents = [...events].sort((a, b) => {
    const aDate = new Date(a.created_at).getTime();
    const bDate = new Date(b.created_at).getTime();

    return (Number.isNaN(bDate) ? 0 : bDate) - (Number.isNaN(aDate) ? 0 : aDate);
  });

  return (
    <section className="sx-panel mt-8 rounded-2xl p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-50">Incident Timeline</h2>
          <p className="mt-1 text-sm text-slate-400">
            Chronological event trail for investigation and resolution evidence.
          </p>
        </div>

        <Badge tone={getStatusTone(incident.status)}>{incident.status}</Badge>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
        <label className="text-sm font-semibold text-slate-300">
          Add investigation note
        </label>

        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={3}
          className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
          placeholder="Example: Engineer reviewed the affected device and confirmed sustained CPU pressure."
        />

        <button
          type="submit"
          disabled={createEventMutation.isPending || !message.trim()}
          className="sx-button-primary mt-3 rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
        >
          {createEventMutation.isPending ? "Adding note..." : "Add note"}
        </button>
      </form>

      {sortedEvents.length === 0 ? (
        <div className="mt-6 rounded-xl border border-slate-800 bg-slate-950/50 p-6 text-sm text-slate-400">
          No timeline events have been recorded.
        </div>
      ) : (
        <div className="mt-6 space-y-4">
          {sortedEvents.map((event) => (
            <article key={event.id} className="relative rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-bold text-slate-50">
                    {formatLabel(event.event_type)}
                  </p>

                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {event.message}
                  </p>

                  <p className="mt-3 text-xs text-slate-500">
                    {formatLabel(event.actor_type)}
                    {event.actor_id ? ` · ${event.actor_id}` : ""} ·{" "}
                    {formatDate(event.created_at)}
                  </p>
                </div>

                <Badge tone="blue">event</Badge>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}