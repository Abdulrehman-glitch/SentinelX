import type { SystemMetric } from "../types/api";

export function getMetricTimestamp(metric: SystemMetric) {
  return (
    metric.created_at ??
    metric.recorded_at ??
    metric.timestamp ??
    metric.updated_at ??
    ""
  );
}

export function formatMetricTimestamp(metric: SystemMetric) {
  const timestamp = getMetricTimestamp(metric);

  if (!timestamp) {
    return "Unknown";
  }

  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatPercent(value?: number | null) {
  if (typeof value !== "number") {
    return "No data";
  }

  return `${value.toFixed(1)}%`;
}

export function getMetricLevel(value?: number | null) {
  if (typeof value !== "number") {
    return {
      label: "No data",
      tone: "slate" as const,
      barClass: "bg-slate-300",
      textClass: "text-slate-700",
    };
  }

  if (value >= 90) {
    return {
      label: "Critical",
      tone: "red" as const,
      barClass: "bg-rose-500",
      textClass: "text-rose-700",
    };
  }

  if (value >= 75) {
    return {
      label: "Warning",
      tone: "amber" as const,
      barClass: "bg-amber-500",
      textClass: "text-amber-700",
    };
  }

  return {
    label: "Normal",
    tone: "green" as const,
    barClass: "bg-emerald-500",
    textClass: "text-emerald-700",
  };
}

export function sortMetricsOldestFirst(metrics: SystemMetric[]) {
  return [...metrics].sort((a, b) => {
    const aDate = new Date(getMetricTimestamp(a)).getTime();
    const bDate = new Date(getMetricTimestamp(b)).getTime();

    return (Number.isNaN(aDate) ? 0 : aDate) - (Number.isNaN(bDate) ? 0 : bDate);
  });
}

export function getLatestMetric(metrics: SystemMetric[]) {
  const sorted = sortMetricsOldestFirst(metrics);

  return sorted.at(-1) ?? null;
}

export function getMetricAverages(metrics: SystemMetric[]) {
  if (metrics.length === 0) {
    return {
      cpu: 0,
      memory: 0,
      disk: 0,
    };
  }

  const totals = metrics.reduce(
    (accumulator, metric) => ({
      cpu: accumulator.cpu + metric.cpu_percent,
      memory: accumulator.memory + metric.memory_percent,
      disk: accumulator.disk + metric.disk_percent,
    }),
    {
      cpu: 0,
      memory: 0,
      disk: 0,
    },
  );

  return {
    cpu: totals.cpu / metrics.length,
    memory: totals.memory / metrics.length,
    disk: totals.disk / metrics.length,
  };
}

export function getMetricPeaks(metrics: SystemMetric[]) {
  if (metrics.length === 0) {
    return {
      cpu: 0,
      memory: 0,
      disk: 0,
    };
  }

  return metrics.reduce(
    (accumulator, metric) => ({
      cpu: Math.max(accumulator.cpu, metric.cpu_percent),
      memory: Math.max(accumulator.memory, metric.memory_percent),
      disk: Math.max(accumulator.disk, metric.disk_percent),
    }),
    {
      cpu: 0,
      memory: 0,
      disk: 0,
    },
  );
}