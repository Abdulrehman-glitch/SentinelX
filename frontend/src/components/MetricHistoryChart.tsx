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
import type { SystemMetric } from "../types/api";
import {
  formatMetricTimestamp,
  getMetricAverages,
  getMetricPeaks,
  sortMetricsOldestFirst,
} from "../utils/metrics";

type MetricHistoryChartProps = {
  metrics: SystemMetric[];
};

type ChartRow = {
  time: string;
  cpu: number;
  memory: number;
  disk: number;
};

function buildChartData(metrics: SystemMetric[]): ChartRow[] {
  return sortMetricsOldestFirst(metrics).map((metric) => ({
    time: formatMetricTimestamp(metric),
    cpu: Number(metric.cpu_percent.toFixed(1)),
    memory: Number(metric.memory_percent.toFixed(1)),
    disk: Number(metric.disk_percent.toFixed(1)),
  }));
}

export function MetricHistoryChart({ metrics }: MetricHistoryChartProps) {
  const chartData = buildChartData(metrics);
  const averages = getMetricAverages(metrics);
  const peaks = getMetricPeaks(metrics);

  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Telemetry Trend
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            CPU, memory, and disk usage history for this device.
          </p>
        </div>

        <div className="grid gap-2 text-xs sm:grid-cols-3">
          <div className="rounded-xl bg-slate-50 px-3 py-2">
            <p className="text-slate-500">Avg CPU</p>
            <p className="font-bold text-slate-950">
              {averages.cpu.toFixed(1)}%
            </p>
          </div>

          <div className="rounded-xl bg-slate-50 px-3 py-2">
            <p className="text-slate-500">Avg Memory</p>
            <p className="font-bold text-slate-950">
              {averages.memory.toFixed(1)}%
            </p>
          </div>

          <div className="rounded-xl bg-slate-50 px-3 py-2">
            <p className="text-slate-500">Avg Disk</p>
            <p className="font-bold text-slate-950">
              {averages.disk.toFixed(1)}%
            </p>
          </div>
        </div>
      </div>

      {chartData.length === 0 ? (
        <div className="mt-6 rounded-xl bg-slate-50 p-6 text-sm text-slate-500">
          No metric history is available yet.
        </div>
      ) : (
        <>
          <div className="mt-6 h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" minTickGap={24} />
                <YAxis domain={[0, 100]} tickFormatter={(value) => `${value}%`} />
                <Tooltip formatter={(value) => `${value}%`} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="cpu"
                  name="CPU"
                  stroke="#0f172a"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="memory"
                  name="Memory"
                  stroke="#64748b"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="disk"
                  name="Disk"
                  stroke="#94a3b8"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Peak CPU</p>
              <p className="mt-1 text-xl font-bold text-slate-950">
                {peaks.cpu.toFixed(1)}%
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Peak Memory</p>
              <p className="mt-1 text-xl font-bold text-slate-950">
                {peaks.memory.toFixed(1)}%
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Peak Disk</p>
              <p className="mt-1 text-xl font-bold text-slate-950">
                {peaks.disk.toFixed(1)}%
              </p>
            </div>
          </div>
        </>
      )}
    </section>
  );
}