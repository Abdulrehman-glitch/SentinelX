import { useState } from "react";
import {
  Activity,
  AlertTriangle,
  ChevronRight,
  Database,
  FileSearch,
  Siren,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import type { Alert, Device, OverviewResponse } from "../types/api";

type StageClasses = {
  card: string;
  iconContainer: string;
  iconText: string;
  count: string;
};

type PipelineStage = {
  key: string;
  icon: LucideIcon;
  label: string;
  sublabel: string;
  detail: string;
  active: StageClasses;
};

const pipelineStages: PipelineStage[] = [
  {
    key: "agent",
    icon: Activity,
    label: "Agent",
    sublabel: "Telemetry",
    detail:
      "Python agent runs on each monitored device. Every polling interval it collects CPU, memory, and disk utilisation via psutil, then posts metrics to the backend API.",
    active: {
      card: "border-cyan-400/40 bg-cyan-400/8",
      iconContainer: "border-cyan-400/30 bg-cyan-400/12 sx-c-info",
      iconText: "sx-c-info",
      count: "sx-c-info",
    },
  },
  {
    key: "ingest",
    icon: Database,
    label: "Ingest",
    sublabel: "Storage",
    detail:
      "Metrics received by the FastAPI backend are persisted to PostgreSQL. The device last_seen_at timestamp is updated on every successful ingest, driving heartbeat-freshness scoring.",
    active: {
      card: "border-blue-400/40 bg-blue-400/7",
      iconContainer: "border-blue-400/30 bg-blue-400/12 sx-c-info",
      iconText: "sx-c-info",
      count: "sx-c-info",
    },
  },
  {
    key: "analyze",
    icon: FileSearch,
    label: "Analyze",
    sublabel: "Rule engine",
    detail:
      "Each ingest triggers rule evaluation. User-defined AlertRule records are evaluated first. Built-in anomaly thresholds (warning: 85%, critical: 95%) act as fallback when no enabled rules match.",
    active: {
      card: "border-violet-400/35 bg-violet-400/7",
      iconContainer: "border-violet-400/30 bg-violet-400/10 sx-c-accent",
      iconText: "sx-c-accent",
      count: "sx-c-accent",
    },
  },
  {
    key: "alert",
    icon: AlertTriangle,
    label: "Alert",
    sublabel: "Detection",
    detail:
      "Threshold violations create Alert records with warning or critical severity. Duplicate alerts are suppressed within rule-defined cooldown windows. All alert events are written to the audit log.",
    active: {
      card: "border-violet-500/30 bg-violet-500/7",
      iconContainer: "border-violet-500/30 bg-violet-500/10 sx-c-accent",
      iconText: "sx-c-accent",
      count: "sx-c-accent",
    },
  },
  {
    key: "incident",
    icon: Siren,
    label: "Incident",
    sublabel: "Escalation",
    detail:
      "Critical alerts automatically open an Incident if no active incident already exists for the same device and metric type. Investigation notes and events can be appended to the incident timeline.",
    active: {
      card: "border-rose-400/40 bg-rose-400/7",
      iconContainer: "border-rose-400/30 bg-rose-400/10 sx-c-danger",
      iconText: "sx-c-danger",
      count: "sx-c-danger",
    },
  },
  {
    key: "recovery",
    icon: Wrench,
    label: "Recovery",
    sublabel: "Self-healing",
    detail:
      "When resource thresholds are sustained, the agent logs a recovery action. A cooldown guard prevents action spam. Recovery actions are traceable in the audit log and visible in the recovery timeline.",
    active: {
      card: "border-emerald-400/35 bg-emerald-400/7",
      iconContainer: "border-emerald-400/30 bg-emerald-400/10 sx-c-success",
      iconText: "sx-c-success",
      count: "sx-c-success",
    },
  },
];

type SystemActivityPanelProps = {
  overview: OverviewResponse | null;
  devices: Device[];
  alerts: Alert[];
};

export function SystemActivityPanel({
  overview,
  devices,
  alerts,
}: SystemActivityPanelProps) {
  const [activeStage, setActiveStage] = useState<string | null>(null);

  const deviceCount = overview?.devices?.total ?? devices.length;
  const metricCount = overview?.metrics?.total ?? 0;
  const unresolvedAlerts = alerts.filter(
    (a) => !a.resolved && !a.is_resolved,
  );
  const alertCount = overview?.alerts?.unresolved ?? unresolvedAlerts.length;
  const incidentCount = overview?.incidents?.open ?? 0;

  const stageCounts: Record<string, string | null> = {
    agent: deviceCount > 0 ? `${deviceCount} device${deviceCount !== 1 ? "s" : ""}` : "None registered",
    ingest: metricCount > 0 ? `${metricCount.toLocaleString()} records` : null,
    analyze: null,
    alert: `${alertCount} unresolved`,
    incident: incidentCount > 0 ? `${incidentCount} open` : "None open",
    recovery: null,
  };

  const activeData = pipelineStages.find((s) => s.key === activeStage) ?? null;

  function toggleStage(key: string) {
    setActiveStage((prev) => (prev === key ? null : key));
  }

  return (
    <section className="sx-panel sx-scanline mt-8 rounded-2xl p-5 sx-animate-in sx-delay-3">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] sx-c-info">
            Monitoring Pipeline
          </p>
          <h2 className="mt-1 text-lg font-bold sx-c-text">
            System Activity Flow
          </h2>
          <p className="mt-1 text-sm sx-c-muted">
            Select any stage to understand how SentinelX monitors, detects, and responds to device telemetry.
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2 self-start rounded-xl border border-emerald-400/20 bg-emerald-400/6 px-3 py-2">
          <span className="sx-live-dot sx-c-success" />
          <span className="text-xs font-bold uppercase tracking-[0.18em] sx-c-success">
            Live
          </span>
        </div>
      </div>

      {/* Pipeline stage grid */}
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {pipelineStages.map((stage, index) => {
          const Icon = stage.icon;
          const isActive = activeStage === stage.key;
          const count = stageCounts[stage.key];

          return (
            <div key={stage.key} className="relative">
              <button
                type="button"
                onClick={() => toggleStage(stage.key)}
                aria-pressed={isActive}
                className={[
                  "sx-flow-node group w-full cursor-pointer rounded-xl border p-3 text-left",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50",
                  isActive
                    ? stage.active.card
                    : "border-slate-700/60 sx-c-surface hover:border-slate-600/70 hover:bg-slate-800/50",
                ].join(" ")}
              >
                <span
                  className={[
                    "mb-2 flex size-8 items-center justify-center rounded-lg border",
                    isActive
                      ? stage.active.iconContainer
                      : "border-slate-700 sx-c-surface sx-c-text0 group-hover:text-slate-400 transition-colors",
                  ].join(" ")}
                >
                  <Icon size={15} strokeWidth={1.8} />
                </span>

                <p
                  className={`text-xs font-bold ${
                    isActive ? stage.active.iconText : "sx-c-muted"
                  }`}
                >
                  {stage.label}
                </p>

                <p className="text-xs sx-c-text0">{stage.sublabel}</p>

                {count && (
                  <p
                    className={`mt-1 text-xs font-semibold ${
                      isActive ? stage.active.count : "text-slate-600"
                    }`}
                  >
                    {count}
                  </p>
                )}
              </button>

              {/* Flow arrow between stages (desktop) */}
              {index < pipelineStages.length - 1 && (
                <div className="absolute -right-2 top-1/2 z-10 hidden -translate-y-1/2 text-slate-600 lg:block">
                  <ChevronRight size={12} strokeWidth={2.5} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Animated flow connector (desktop) */}
      <div className="mt-3 hidden h-px lg:block">
        <div className="sx-flow-connector h-full bg-slate-700/30 rounded-full" />
      </div>

      {/* Stage detail expansion */}
      {activeData && (
        <div className="mt-4 rounded-xl border border-slate-700/50 sx-c-surface p-4 sx-animate-in">
          <div className="flex items-center gap-3">
            <span
              className={[
                "flex size-9 items-center justify-center rounded-xl border border-slate-700 sx-c-surface",
                activeData.active.iconText,
              ].join(" ")}
            >
              <activeData.icon size={17} strokeWidth={1.8} />
            </span>
            <div>
              <p className="text-sm font-bold sx-c-text">
                {activeData.label}
              </p>
              <p className="text-xs sx-c-muted">{activeData.sublabel}</p>
            </div>
          </div>
          <p className="mt-3 text-sm leading-6 sx-c-muted">
            {activeData.detail}
          </p>
        </div>
      )}
    </section>
  );
}
