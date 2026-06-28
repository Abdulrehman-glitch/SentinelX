import { Activity, FileText, ShieldAlert, Wrench } from "lucide-react";
import type { ComponentType } from "react";
import { Link } from "react-router";
import type { StreamEvent, StreamEventKind } from "../utils/dashboard";
import { relativeTime } from "../utils/dashboard";

const KIND_ICON: Record<
  StreamEventKind,
  ComponentType<{ size: number; strokeWidth: number; className?: string; "aria-hidden"?: boolean }>
> = {
  alert:    ShieldAlert,
  recovery: Wrench,
  audit:    FileText,
};

const SEV_LEFT_CLASS: Record<string, string> = {
  critical: "dc-sev-critical",
  warning:  "dc-sev-warning",
  info:     "dc-sev-info",
  resolved: "dc-sev-resolved",
};

const SEV_ICON_COLOR: Record<string, string> = {
  critical: "#f43f5e",
  warning:  "#f59e0b",
  info:     "#818cf8",
  resolved: "var(--sx-dim)",
};

type LiveEventStreamProps = {
  events: StreamEvent[];
  isLoading: boolean;
};

function EventRow({ event }: { event: StreamEvent }) {
  const Icon      = KIND_ICON[event.kind] ?? Activity;
  const leftClass = SEV_LEFT_CLASS[event.severity] ?? SEV_LEFT_CLASS.info;
  const iconColor = SEV_ICON_COLOR[event.severity] ?? SEV_ICON_COLOR.info;

  return (
    <Link
      to={event.href}
      className={`dc-event-item group block px-3.5 py-2.5 focus-visible:outline-none ${leftClass}`}
    >
      <div className="flex items-start gap-2">
        <Icon
          size={10}
          strokeWidth={2.5}
          className="mt-0.5 shrink-0"
          style={{ color: iconColor } as React.CSSProperties}
          aria-hidden={true}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <p
              className="dc-mono truncate text-[11px] font-medium transition-colors group-hover:text-slate-100"
              style={{ color: "var(--sx-muted)" }}
            >
              {event.headline}
            </p>
            <p
              className="dc-mono shrink-0 tabular-nums text-[9px]"
              style={{ color: "var(--sx-dim)" }}
            >
              {relativeTime(event.timestamp)}
            </p>
          </div>
          {event.detail && (
            <p
              className="mt-0.5 truncate text-[10px] leading-4 transition-colors group-hover:text-slate-500"
              style={{ color: "var(--sx-dim)" }}
            >
              {event.detail}
            </p>
          )}
        </div>
      </div>
    </Link>
  );
}

function Skeleton() {
  return (
    <div className="space-y-px" aria-busy="true" aria-label="Loading events">
      {Array.from({ length: 10 }).map((_, i) => (
        <div
          key={i}
          className="flex items-start gap-2 border-l-2 px-3.5 py-2.5"
          style={{ borderColor: "var(--sx-border-md)" }}
        >
          <div
            className="mt-0.5 h-2.5 w-2.5 shrink-0 animate-pulse rounded"
            style={{ background: "var(--sx-dim)", opacity: 0.4, animationDelay: `${i * 0.04}s` }}
          />
          <div className="flex-1 space-y-1.5">
            <div
              className="h-2.5 animate-pulse rounded"
              style={{
                width: `${60 + (i % 4) * 18}px`,
                background: "var(--sx-dim)",
                opacity: 0.35,
                animationDelay: `${i * 0.04}s`,
              }}
            />
            <div
              className="h-2 animate-pulse rounded"
              style={{ width: `${90 + (i % 3) * 20}px`, background: "var(--sx-dim)", opacity: 0.2 }}
            />
          </div>
          <div
            className="h-2 w-7 animate-pulse rounded"
            style={{ background: "var(--sx-dim)", opacity: 0.2 }}
          />
        </div>
      ))}
    </div>
  );
}

export function LiveEventStream({ events, isLoading }: LiveEventStreamProps) {
  const criticalCount = events.filter((e) => e.severity === "critical").length;

  return (
    <div className="flex h-full flex-col">
      {/* Panel header */}
      <div
        className="flex shrink-0 items-center justify-between border-b px-4 py-3"
        style={{ borderColor: "var(--sx-border)" }}
      >
        <div className="flex items-center gap-2">
          <Activity size={11} strokeWidth={2} style={{ color: "var(--sx-dim)" }} aria-hidden="true" />
          <span className="dc-label">Event Stream</span>
        </div>
        <div className="flex items-center gap-2.5">
          {criticalCount > 0 && (
            <span
              className="dc-mono text-[10px] font-bold"
              style={{ color: "#f43f5e" }}
              aria-label={`${criticalCount} critical events`}
            >
              {criticalCount} crit
            </span>
          )}
          <span
            className="dc-mono text-[10px]"
            style={{ color: "var(--sx-dim)" }}
            aria-label={`${events.length} total events`}
          >
            {events.length}
          </span>
        </div>
      </div>

      {/* Event list */}
      <div
        className="max-h-[360px] overflow-y-auto lg:max-h-none lg:flex-1 lg:min-h-0"
        aria-label="Live event feed"
        aria-live="polite"
        aria-atomic="false"
      >
        {isLoading && events.length === 0 ? (
          <Skeleton />
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
            <Activity size={20} strokeWidth={1.5} style={{ color: "var(--sx-dim)" }} aria-hidden="true" />
            <p className="dc-mono mt-3 text-xs" style={{ color: "var(--sx-dim)" }}>
              No events recorded yet.
            </p>
          </div>
        ) : (
          events.map((event) => <EventRow key={event.key} event={event} />)
        )}
      </div>
    </div>
  );
}
