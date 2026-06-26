import { Badge, getStatusTone } from "./Badge";
import type { DeviceHealth, SystemMetric } from "../types/api";

type HealthScorePanelProps = {
  health?: DeviceHealth | null;
  latestMetrics?: SystemMetric | null;
};

function getScore(health?: DeviceHealth | null, latestMetrics?: SystemMetric | null) {
  if (typeof health?.health_score === "number") {
    return health.health_score;
  }

  if (typeof health?.score === "number") {
    return health.score;
  }

  if (!latestMetrics) {
    return null;
  }

  const worstMetric = Math.max(
    latestMetrics.cpu_percent,
    latestMetrics.memory_percent,
    latestMetrics.disk_percent,
  );

  return Math.max(0, Math.round(100 - worstMetric));
}

function getStatusFromScore(score: number | null, explicitStatus?: string) {
  if (explicitStatus) {
    return explicitStatus;
  }

  if (score === null) {
    return "unknown";
  }

  if (score >= 80) {
    return "healthy";
  }

  if (score >= 60) {
    return "warning";
  }

  return "critical";
}

function getBarClass(score: number | null) {
  if (score === null) {
    return "bg-slate-300";
  }

  if (score >= 80) {
    return "bg-emerald-500";
  }

  if (score >= 60) {
    return "bg-amber-500";
  }

  return "bg-rose-500";
}

export function HealthScorePanel({
  health,
  latestMetrics,
}: HealthScorePanelProps) {
  const score = getScore(health, latestMetrics);
  const status = getStatusFromScore(score, health?.status ?? health?.level);
  const reasons = health?.reasons ?? [];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Device Health Score
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Calculated from current telemetry and alert state.
          </p>
        </div>

        <Badge tone={getStatusTone(status)}>{status}</Badge>
      </div>

      <div className="mt-6">
        <p className="text-5xl font-bold tracking-tight text-slate-950">
          {score === null ? "N/A" : `${Math.round(score)}`}
          <span className="text-lg font-semibold text-slate-400"> / 100</span>
        </p>

        <div className="mt-4 h-3 overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full transition-all ${getBarClass(score)}`}
            style={{ width: `${score === null ? 0 : Math.max(0, Math.min(score, 100))}%` }}
          />
        </div>
      </div>

      <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
        <p className="font-medium text-slate-900">
          {health?.message ?? health?.reason ?? "Health score is based on the latest available monitoring data."}
        </p>

        {reasons.length > 0 && (
          <ul className="mt-3 list-disc space-y-1 pl-5">
            {reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}