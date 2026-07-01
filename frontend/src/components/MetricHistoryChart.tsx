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
    <section className="sx-panel mt-8 rounded-2xl p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-50">Telemetry Trend</h2>

          <p className="mt-1 text-sm leading-6 text-slate-400">
            CPU, memory, and disk usage history for this device.
          </p>
        </div>

        <div className="grid gap-2 text-xs sm:grid-cols-3">
          <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
            <p className="text-slate-500">Avg CPU</p>
            <p className="font-bold text-slate-50">
              {averages.cpu.toFixed(1)}%
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
            <p className="text-slate-500">Avg Memory</p>
            <p className="font-bold text-slate-50">
              {averages.memory.toFixed(1)}%
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
            <p className="text-slate-500">Avg Disk</p>
            <p className="font-bold text-slate-50">
              {averages.disk.toFixed(1)}%
            </p>
          </div>
        </div>
      </div>

      {chartData.length === 0 ? (
        <div className="mt-6 rounded-xl border border-slate-800 bg-slate-950/60 p-6 text-sm text-slate-400">
          No metric history is available yet.
        </div>
      ) : (
        <>
          <div className="mt-6 h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={chartData}
                margin={{ top: 10, right: 20, left: 0, bottom: 10 }}
              >
                <CartesianGrid stroke="rgba(148,163,184,0.16)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="time"
                  minTickGap={24}
                  tick={{ fill: "#94a3b8", fontSize: 12 }}
                  axisLine={{ stroke: "rgba(148,163,184,0.18)" }}
                  tickLine={{ stroke: "rgba(148,163,184,0.18)" }}
                />
                <YAxis
                  domain={[0, 100]}
                  tickFormatter={(value) => `${value}%`}
                  tick={{ fill: "#94a3b8", fontSize: 12 }}
                  axisLine={{ stroke: "rgba(148,163,184,0.18)" }}
                  tickLine={{ stroke: "rgba(148,163,184,0.18)" }}
                />
                <Tooltip
                  formatter={(value) => `${value}%`}
                  contentStyle={{
                    background: "rgba(2, 6, 23, 0.94)",
                    border: "1px solid rgba(148, 163, 184, 0.22)",
                    borderRadius: "14px",
                    color: "#e2e8f0",
                  }}
                  labelStyle={{ color: "#93c5fd" }}
                />
                <Legend wrapperStyle={{ color: "#cbd5e1" }} />
                <Line
                  type="monotone"
                  dataKey="cpu"
                  name="CPU"
                  stroke="#38bdf8"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="memory"
                  name="Memory"
                  stroke="#16a34a"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="disk"
                  name="Disk"
                  stroke="#d97706"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p className="text-sm text-slate-500">Peak CPU</p>
              <p className="mt-1 text-xl font-bold text-slate-50">
                {peaks.cpu.toFixed(1)}%
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p className="text-sm text-slate-500">Peak Memory</p>
              <p className="mt-1 text-xl font-bold text-slate-50">
                {peaks.memory.toFixed(1)}%
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p className="text-sm text-slate-500">Peak Disk</p>
              <p className="mt-1 text-xl font-bold text-slate-50">
                {peaks.disk.toFixed(1)}%
              </p>
            </div>
          </div>
        </>
      )}
    </section>
  );
}