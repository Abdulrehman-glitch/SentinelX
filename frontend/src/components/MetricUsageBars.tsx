import { Badge } from "./Badge";
import type { SystemMetric } from "../types/api";
import { formatPercent, getMetricLevel } from "../utils/metrics";

type MetricUsageBarsProps = {
  latestMetrics?: SystemMetric | null;
};

type MetricRowProps = {
  label: string;
  value?: number | null;
};

function MetricRow({ label, value }: MetricRowProps) {
  const level = getMetricLevel(value);
  const safeValue =
    typeof value === "number" ? Math.max(0, Math.min(value, 100)) : 0;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-950">{label}</p>
          <p className={`text-xs font-medium ${level.textClass}`}>
            {level.label}
          </p>
        </div>

        <p className="text-sm font-bold text-slate-950">
          {formatPercent(value)}
        </p>
      </div>

      <div className="h-3 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full transition-all ${level.barClass}`}
          style={{ width: `${safeValue}%` }}
        />
      </div>
    </div>
  );
}

export function MetricUsageBars({ latestMetrics }: MetricUsageBarsProps) {
  const highest =
    latestMetrics === null || latestMetrics === undefined
      ? null
      : Math.max(
          latestMetrics.cpu_percent,
          latestMetrics.memory_percent,
          latestMetrics.disk_percent,
        );

  const level = getMetricLevel(highest);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Current Resource Usage
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Latest CPU, memory, and disk usage reported by the agent.
          </p>
        </div>

        <Badge tone={level.tone}>{level.label}</Badge>
      </div>

      <div className="mt-6 space-y-5">
        <MetricRow label="CPU" value={latestMetrics?.cpu_percent} />
        <MetricRow label="Memory" value={latestMetrics?.memory_percent} />
        <MetricRow label="Disk" value={latestMetrics?.disk_percent} />
      </div>
    </section>
  );
}