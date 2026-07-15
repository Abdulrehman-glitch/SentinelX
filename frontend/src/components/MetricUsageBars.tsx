import type { SystemMetric } from "../types/api";
import { formatPercent, getMetricLevel } from "../utils/metrics";
import { Badge } from "./Badge";

type MetricUsageBarsProps = {
  latestMetrics?: SystemMetric | null;
};

function MetricRow({ label, value }: { label: string; value?: number | null }) {
  const level     = getMetricLevel(value);
  const safeValue = typeof value === "number" ? Math.max(0, Math.min(value, 100)) : 0;

  const barColor =
    level.tone === "red"   ? "var(--sx-red)" :
    level.tone === "amber" ? "var(--sx-amber)" :
    "var(--sx-green)";

  const labelColor =
    level.tone === "red"   ? "var(--sx-red)" :
    level.tone === "amber" ? "var(--sx-amber)" :
    "var(--sx-green)";

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium" style={{ color: "var(--sx-text)" }}>{label}</p>
          <p className="text-xs font-medium" style={{ color: labelColor }}>{level.label}</p>
        </div>
        <p
          className="text-sm font-bold tabular-nums"
          style={{ color: "var(--sx-text)", fontFamily: "var(--font-mono)" }}
        >
          {formatPercent(value)}
        </p>
      </div>

      <div className="h-2 overflow-hidden rounded-full" style={{ background: "var(--sx-border-md)" }}>
        <div
          className="h-full rounded-full sx-bar-animated"
          style={{ width: `${safeValue}%`, background: barColor }}
        />
      </div>
    </div>
  );
}

export function MetricUsageBars({ latestMetrics }: MetricUsageBarsProps) {
  const highest =
    latestMetrics == null
      ? null
      : Math.max(latestMetrics.cpu_percent, latestMetrics.memory_percent, latestMetrics.disk_percent);

  const level = getMetricLevel(highest);

  return (
    <section className="sx-panel p-5 sx-animate-in sx-delay-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold" style={{ color: "var(--sx-text)" }}>
            Current Resource Usage
          </h2>
          <p className="mt-1 text-sm" style={{ color: "var(--sx-muted)" }}>
            Latest CPU, memory, and disk usage reported by the agent.
          </p>
        </div>
        <Badge tone={level.tone}>{level.label}</Badge>
      </div>

      <div className="mt-6 space-y-5">
        <MetricRow label="CPU"    value={latestMetrics?.cpu_percent}    />
        <MetricRow label="Memory" value={latestMetrics?.memory_percent} />
        <MetricRow label="Disk"   value={latestMetrics?.disk_percent}   />
      </div>
    </section>
  );
}
