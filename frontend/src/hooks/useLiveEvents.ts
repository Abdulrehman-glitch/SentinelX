/**
 * Turns live events into cache invalidations.
 *
 * The deliberate choice here is that live events do not carry state into the
 * app. A frame says "incident 7 changed"; this hook marks the incident queries
 * stale and TanStack Query refetches them through the same API every other
 * part of the console uses. So there is exactly one path data can arrive by,
 * and the live channel is an optimisation over polling rather than a second,
 * subtly different copy of the truth that can drift from the first.
 *
 * It also means switching the stream off changes only how quickly the console
 * notices things, never what it shows.
 */

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { connectLiveStream, type LiveEvent, type LiveStatus } from "../lib/liveStream";
import { queryKeys } from "../lib/queryKeys";

/**
 * Which cached queries each event type makes stale.
 *
 * Prefixes, not exact keys: TanStack Query matches partially, so invalidating
 * ["incidents"] also refreshes ["incidents", id] and its events. An event type
 * that is not listed is still delivered to subscribers - it simply does not
 * invalidate anything on its own.
 */
const INVALIDATIONS: Record<string, readonly (readonly unknown[])[]> = {
  "alert.created": [queryKeys.alerts, queryKeys.overview, queryKeys.devices],
  "alert.updated": [queryKeys.alerts, queryKeys.overview],
  "incident.created": [queryKeys.incidents, queryKeys.overview],
  "incident.updated": [queryKeys.incidents, queryKeys.overview],
  "device.status_changed": [queryKeys.devices, queryKeys.overview],
  "recovery.state_changed": [queryKeys.recoveryCommands, queryKeys.recoveryActions],
  "telemetry.batch_accepted": [queryKeys.devices],
  "system.degraded": [queryKeys.health],
};

export type UseLiveEventsResult = {
  status: LiveStatus;
  /** The most recent events, newest first. Bounded - this is a ticker, not a log. */
  recent: LiveEvent[];
  lastEventAt: Date | null;
};

const MAX_RECENT = 50;

export function useLiveEvents(options: { enabled?: boolean } = {}): UseLiveEventsResult {
  const { enabled = true } = options;
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const [recent, setRecent] = useState<LiveEvent[]>([]);
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);

  useEffect(() => {
    if (!enabled) {
      setStatus("offline");
      return;
    }

    const stop = connectLiveStream({
      onStatus: setStatus,
      onEvent: (event) => {
        for (const key of INVALIDATIONS[event.type] ?? []) {
          void queryClient.invalidateQueries({ queryKey: key });
        }
        setLastEventAt(new Date());
        setRecent((previous) => [event, ...previous].slice(0, MAX_RECENT));
      },
    });

    return stop;
    // queryClient is the stable instance from context, so this effect runs
    // once per mount - the connection is not torn down on every render.
  }, [enabled, queryClient]);

  return { status, recent, lastEventAt };
}

/** Human-facing wording for each connection state, used by the indicator. */
export const LIVE_STATUS_LABEL: Record<LiveStatus, string> = {
  connecting: "Connecting",
  live: "Live",
  reconnecting: "Reconnecting",
  stale: "Stale",
  offline: "Offline",
};

/**
 * What each state means for the data on screen. Status is never signalled by
 * colour alone; this is the text that accompanies it.
 */
export const LIVE_STATUS_DESCRIPTION: Record<LiveStatus, string> = {
  connecting: "Opening the live channel.",
  live: "Updates arrive as they happen.",
  reconnecting: "Live updates paused. Data still loads normally.",
  stale: "The live channel has gone quiet. Data still loads normally.",
  offline: "Live updates unavailable. Refresh to load the latest.",
};
