import type { DeviceHealth, SystemMetric } from "../types/api";
import { Badge, getStatusTone } from "./Badge";

type HealthScorePanelProps = {
  health?: DeviceHealth | null;
  latestMetrics?: SystemMetric | null;
};

function getScore(health?: DeviceHealth | null, latestMetrics?: SystemMetric | null) {
  if (typeof health?.health_score === "number") return health.health_score;
  if (typeof health?.score === "number")        return health.score;
  if (!latestMetrics) return null;
  const worstMetric = Math.max(
    latestMetrics.cpu_percent,
    latestMetrics.memory_percent,
    latestMetrics.disk_percent,
  );
  return Math.max(0, Math.round(100 - worstMetric));
}

function getStatusFromScore(score: number | null, explicitStatus?: string) {
  if (explicitStatus) return explicitStatus;
  if (score === null)  return "unknown";
  if (score >= 80)     return "healthy";
  if (score >= 60)     return "warning";
  return "critical";
}

function getBarColor(score: number | null) {
  if (score === null) return "var(--sx-dim)";
  if (score >= 80)    return "#22c55e";
  if (score >= 60)    return "#c8102e";
  return "#e11d48";
}

function getScoreColor(score: number | null) {
  if (score === null) return "var(--sx-muted)";
  if (score >= 80)    return "#4ade80";
  if (score >= 60)    return "#d97706";
  return "#fb7185";
}

export function HealthScorePanel({ health, latestMetrics }: HealthScorePanelProps) {
  const score  = getScore(health, latestMetrics);
  const status = getStatusFromScore(score, health?.status ?? health?.level);
  const reasons = health?.reasons ?? [];

  return (
    <section className="sx-panel p-5 sx-animate-in sx-delay-2">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold" style={{ color: "var(--sx-text)" }}>
            Device Health Score
          </h2>
          <p className="mt-1 text-sm" style={{ color: "var(--sx-muted)" }}>
            Calculated from current telemetry and alert state.
          </p>
        </div>
        <Badge tone={getStatusTone(status)}>{status}</Badge>
      </div>

      <div className="mt-6">
        <p
          className="text-5xl font-bold tracking-tight"
          style={{ color: getScoreColor(score), fontFamily: "var(--font-ui)" }}
        >
          {score === null ? "N/A" : Math.round(score)}
          <span className="text-lg font-medium" style={{ color: "var(--sx-dim)" }}> / 100</span>
        </p>

        <div
          className="mt-4 h-2 overflow-hidden rounded-full"
          style={{ background: "var(--sx-border-md)" }}
        >
          <div
            className="h-full rounded-full sx-bar-animated"
            style={{
              width: `${score === null ? 0 : Math.max(0, Math.min(score, 100))}%`,
              background: getBarColor(score),
            }}
          />
        </div>
      </div>

      <div
        className="mt-5 rounded-lg border p-4 text-sm"
        style={{
          borderColor: "var(--sx-border-md)",
          background: "var(--sx-bg)",
          color: "var(--sx-muted)",
        }}
      >
        <p className="font-medium" style={{ color: "var(--sx-text)" }}>
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
