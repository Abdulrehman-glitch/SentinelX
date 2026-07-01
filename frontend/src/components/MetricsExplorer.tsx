import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { MetricsHistoryTable } from "./MetricsHistoryTable";
import { Badge } from "./Badge";
import { useDevicesQuery } from "../hooks/useDevicesQuery";
import { useDeviceMetricHistoryQuery } from "../hooks/useDeviceMetricHistoryQuery";
import { useDeviceLatestMetricsQuery } from "../hooks/useDeviceLatestMetricsQuery";
import type { Device, SystemMetric } from "../types/api";
import {
  formatMetricTimestamp,
  getMetricAverages,
  getMetricPeaks,
  sortMetricsOldestFirst,
} from "../utils/metrics";
import { downloadCsv } from "../utils/csv";

type MetricKey = "all" | "cpu_percent" | "memory_percent" | "disk_percent";

function getDeviceId(device: Device) {
  return device.id ?? device.device_id ?? "";
}

function buildChartData(metrics: SystemMetric[]) {
  return sortMetricsOldestFirst(metrics).map((metric) => ({
    time: formatMetricTimestamp(metric),
    cpu: Number(metric.cpu_percent.toFixed(1)),
    memory: Number(metric.memory_percent.toFixed(1)),
    disk: Number(metric.disk_percent.toFixed(1)),
  }));
}

function getSelectedMetricLabel(metricKey: MetricKey) {
  if (metricKey === "cpu_percent") {
    return "CPU";
  }

  if (metricKey === "memory_percent") {
    return "Memory";
  }

  if (metricKey === "disk_percent") {
    return "Disk";
  }

  return "All metrics";
}

export function MetricsExplorer() {
  const devicesQuery = useDevicesQuery();

  const firstDeviceId = devicesQuery.data?.[0]
    ? getDeviceId(devicesQuery.data[0])
    : "";

  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [metricKey, setMetricKey] = useState<MetricKey>("all");
  const [limit, setLimit] = useState(100);

  const activeDeviceId = selectedDeviceId || firstDeviceId;

  const metricHistoryQuery = useDeviceMetricHistoryQuery(activeDeviceId, limit);
  const latestMetricsQuery = useDeviceLatestMetricsQuery(activeDeviceId);

  const metrics = metricHistoryQuery.data ?? [];
  const chartData = useMemo(() => buildChartData(metrics), [metrics]);
  const averages = getMetricAverages(metrics);
  const peaks = getMetricPeaks(metrics);
  const latest = latestMetricsQuery.data;

  function handleExportCsv() {
    downloadCsv(
      `sentinelx-metrics-${activeDeviceId || "device"}.csv`,
      metrics.map((metric) => ({
        device_id: metric.device_id ?? activeDeviceId,
        timestamp:
          metric.created_at ??
          metric.recorded_at ??
          metric.timestamp ??
          metric.updated_at ??
          "",
        cpu_percent: metric.cpu_percent,
        memory_percent: metric.memory_percent,
        disk_percent: metric.disk_percent,
      })),
    );
  }

  const selectedDevice = devicesQuery.data?.find(
    (device) => getDeviceId(device) === activeDeviceId,
  );

  return (
    <>
      <section className="sx-panel rounded-2xl p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-50">Metrics Explorer</h2>

            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
              Explore CPU, memory, and disk telemetry for a selected device. This
              uses the existing device metric history endpoint.
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-4">
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Device
              </label>
              <select
                value={activeDeviceId}
                onChange={(event) => setSelectedDeviceId(event.target.value)}
                className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
              >
                {(devicesQuery.data ?? []).map((device) => {
                  const deviceId = getDeviceId(device);

                  return (
                    <option key={deviceId} value={deviceId}>
                      {device.hostname}
                    </option>
                  );
                })}
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Metric
              </label>
              <select
                value={metricKey}
                onChange={(event) => setMetricKey(event.target.value as MetricKey)}
                className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
              >
                <option value="all">All metrics</option>
                <option value="cpu_percent">CPU</option>
                <option value="memory_percent">Memory</option>
                <option value="disk_percent">Disk</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Records
              </label>
              <select
                value={limit}
                onChange={(event) => setLimit(Number(event.target.value))}
                className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
              >
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
              </select>
            </div>

            <button
              type="button"
              onClick={handleExportCsv}
              disabled={metrics.length === 0}
              className="sx-button-primary mt-6 rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              Export CSV
            </button>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <Badge tone="blue">
            {selectedDevice?.hostname ?? "No device"}
          </Badge>
          <Badge tone="slate">{getSelectedMetricLabel(metricKey)}</Badge>
          <Badge tone="green">{metrics.length} records</Badge>
        </div>
      </section>

      <section className="mt-8 grid gap-4 lg:grid-cols-3">
        <article className="sx-panel rounded-2xl p-5">
          <p className="text-sm font-semibold text-slate-400">Latest CPU</p>
          <p className="mt-3 text-4xl font-bold text-slate-50">
            {latest ? `${latest.cpu_percent.toFixed(1)}%` : "N/A"}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Avg {averages.cpu.toFixed(1)}% · Peak {peaks.cpu.toFixed(1)}%
          </p>
        </article>

        <article className="sx-panel rounded-2xl p-5">
          <p className="text-sm font-semibold text-slate-400">Latest Memory</p>
          <p className="mt-3 text-4xl font-bold text-slate-50">
            {latest ? `${latest.memory_percent.toFixed(1)}%` : "N/A"}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Avg {averages.memory.toFixed(1)}% · Peak {peaks.memory.toFixed(1)}%
          </p>
        </article>

        <article className="sx-panel rounded-2xl p-5">
          <p className="text-sm font-semibold text-slate-400">Latest Disk</p>
          <p className="mt-3 text-4xl font-bold text-slate-50">
            {latest ? `${latest.disk_percent.toFixed(1)}%` : "N/A"}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Avg {averages.disk.toFixed(1)}% · Peak {peaks.disk.toFixed(1)}%
          </p>
        </article>
      </section>

      <section className="sx-panel mt-8 rounded-2xl p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-50">
              Explorer Chart
            </h2>
            <p className="mt-1 text-sm text-slate-400">
              Filtered telemetry view for the selected metric.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              metricHistoryQuery.refetch();
              latestMetricsQuery.refetch();
            }}
            className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold"
          >
            Refresh metrics
          </button>
        </div>

        {chartData.length === 0 ? (
          <div className="mt-6 rounded-xl border border-white/[0.056] bg-black/30 p-6 text-sm text-slate-400">
            No metrics available for this device yet.
          </div>
        ) : (
          <div className="mt-6 h-96">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="time"
                  minTickGap={24}
                  tick={{ fill: "#94a3b8", fontSize: 12 }}
                />
                <YAxis
                  domain={[0, 100]}
                  tickFormatter={(value) => `${value}%`}
                  tick={{ fill: "#94a3b8", fontSize: 12 }}
                />
                <Tooltip
                  formatter={(value) => `${value}%`}
                  contentStyle={{
                    background: "#0f1119",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: "12px",
                    color: "#e5e7eb",
                  }}
                />
                <Legend />

                {(metricKey === "all" || metricKey === "cpu_percent") && (
                  <Line
                    type="monotone"
                    dataKey="cpu"
                    name="CPU"
                    stroke="#4f46e5"
                    strokeWidth={2}
                    dot={false}
                  />
                )}

                {(metricKey === "all" || metricKey === "memory_percent") && (
                  <Line
                    type="monotone"
                    dataKey="memory"
                    name="Memory"
                    stroke="#22c55e"
                    strokeWidth={2}
                    dot={false}
                  />
                )}

                {(metricKey === "all" || metricKey === "disk_percent") && (
                  <Line
                    type="monotone"
                    dataKey="disk"
                    name="Disk"
                    stroke="#e11d48"
                    strokeWidth={2}
                    dot={false}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      <MetricsHistoryTable metrics={metrics} />
    </>
  );
}