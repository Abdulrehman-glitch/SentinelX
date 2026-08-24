/**
 * The console's honesty about its own freshness.
 *
 * Status is never carried by colour alone: every state has a label, a distinct
 * icon shape, and a `title` explaining what it means for the data on screen. A
 * dot that silently turns amber is useless to a colour-blind operator and only
 * marginally better for anyone else.
 */

import { Activity, PauseCircle, Radio, WifiOff } from "lucide-react";

import { LIVE_STATUS_DESCRIPTION, LIVE_STATUS_LABEL } from "../hooks/useLiveEvents";
import type { LiveStatus } from "../lib/liveStream";

const PRESENTATION: Record<
  LiveStatus,
  { icon: typeof Radio; className: string; pulse: boolean }
> = {
  live: { icon: Radio, className: "sx-live-ok", pulse: true },
  connecting: { icon: Activity, className: "sx-live-pending", pulse: true },
  reconnecting: { icon: Activity, className: "sx-live-pending", pulse: true },
  stale: { icon: PauseCircle, className: "sx-live-warn", pulse: false },
  offline: { icon: WifiOff, className: "sx-live-off", pulse: false },
};

export function LiveStatusIndicator({
  status,
  lastEventAt,
  compact = false,
}: {
  status: LiveStatus;
  lastEventAt?: Date | null;
  compact?: boolean;
}) {
  const { icon: Icon, className, pulse } = PRESENTATION[status];
  const description = LIVE_STATUS_DESCRIPTION[status];

  return (
    <span
      className={`sx-live-indicator ${className}`}
      title={description}
      // Polite: freshness changes must not interrupt whatever a screen-reader
      // user is currently reading.
      aria-live="polite"
    >
      <Icon
        size={14}
        aria-hidden="true"
        className={pulse ? "sx-live-indicator-icon sx-live-pulse" : "sx-live-indicator-icon"}
      />
      <span className="sx-live-indicator-label">{LIVE_STATUS_LABEL[status]}</span>
      <span className="sr-only">{description}</span>
      {!compact && lastEventAt ? (
        <span className="sx-live-indicator-time">
          {lastEventAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      ) : null}
    </span>
  );
}
