import { Activity, ChevronLeft, ChevronRight, FileText, ShieldAlert, Wrench } from "lucide-react";
import { useState } from "react";
import type { ComponentType } from "react";
import { Link } from "react-router";
import type { StreamEvent, StreamEventKind } from "../utils/dashboard";
import { relativeTime } from "../utils/dashboard";

const EVENTS_PER_PAGE = 10;

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
  critical: "#e11d48",
  warning:  "#4f46e5",
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
        <span className="mt-0.5 shrink-0" style={{ color: iconColor }}>
          <Icon size={10} strokeWidth={2.5} aria-hidden={true} />
        </span>
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
      {Array.from({ length: EVENTS_PER_PAGE }).map((_, i) => (
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
  const [page, setPage] = useState(0);

  const totalPages = Math.max(1, Math.ceil(events.length / EVENTS_PER_PAGE));
  const safePage = Math.min(page, totalPages - 1);
  const pagedEvents = events.slice(safePage * EVENTS_PER_PAGE, (safePage + 1) * EVENTS_PER_PAGE);
  const criticalCount = events.filter((e) => e.severity === "critical").length;

  function prevPage() { setPage((p) => Math.max(0, p - 1)); }
  function nextPage() { setPage((p) => Math.min(totalPages - 1, p + 1)); }

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
              style={{ color: "#e11d48" }}
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
        className="flex-1 overflow-y-auto"
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
          pagedEvents.map((event) => <EventRow key={event.key} event={event} />)
        )}
      </div>

      {/* Pagination footer */}
      {events.length > 0 && (
        <div
          className="flex shrink-0 items-center justify-between border-t px-4 py-2"
          style={{ borderColor: "var(--sx-border)" }}
        >
          <button
            type="button"
            onClick={prevPage}
            disabled={safePage === 0}
            aria-label="Previous page"
            className="dc-page-btn"
            style={{
              opacity: safePage === 0 ? 0.3 : 1,
              cursor: safePage === 0 ? "not-allowed" : "pointer",
            }}
          >
            <ChevronLeft size={12} strokeWidth={2} />
          </button>

          <span className="dc-mono text-[9px] tabular-nums" style={{ color: "var(--sx-dim)" }}>
            {safePage + 1} / {totalPages}
            <span className="ml-1.5" style={{ color: "var(--sx-dim)", opacity: 0.5 }}>
              ({events.length} events)
            </span>
          </span>

          <button
            type="button"
            onClick={nextPage}
            disabled={safePage >= totalPages - 1}
            aria-label="Next page"
            className="dc-page-btn"
            style={{
              opacity: safePage >= totalPages - 1 ? 0.3 : 1,
              cursor: safePage >= totalPages - 1 ? "not-allowed" : "pointer",
            }}
          >
            <ChevronRight size={12} strokeWidth={2} />
          </button>
        </div>
      )}
    </div>
  );
}
