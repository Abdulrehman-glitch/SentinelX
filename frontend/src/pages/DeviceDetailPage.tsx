import { Link, useParams } from "react-router";
import { HealthScorePanel } from "../components/HealthScorePanel";
import { MetricCard } from "../components/MetricCard";
import { MetricsHistoryTable } from "../components/MetricsHistoryTable";
import { Badge, getStatusTone } from "../components/Badge";
import { useDeviceHealthQuery } from "../hooks/useDeviceHealthQuery";
import { useDeviceLatestMetricsQuery } from "../hooks/useDeviceLatestMetricsQuery";
import { useDeviceMetricHistoryQuery } from "../hooks/useDeviceMetricHistoryQuery";
import { useDeviceQuery } from "../hooks/useDeviceQuery";
import { useDeviceSummaryQuery } from "../hooks/useDeviceSummaryQuery";
import { formatDate } from "../utils/format";

export function DeviceDetailPage() {
  const params = useParams();
  const deviceId = params.deviceId ?? "";

  const deviceQuery = useDeviceQuery(deviceId);
  const latestMetricsQuery = useDeviceLatestMetricsQuery(deviceId);
  const metricHistoryQuery = useDeviceMetricHistoryQuery(deviceId, 100);
  const healthQuery = useDeviceHealthQuery(deviceId);
  const summaryQuery = useDeviceSummaryQuery(deviceId);

  const device = summaryQuery.data?.device ?? deviceQuery.data ?? null;
  const latestMetrics =
    summaryQuery.data?.latest_metrics ??
    summaryQuery.data?.latest_metric ??
    latestMetricsQuery.data ??
    null;

  const health = summaryQuery.data?.health ?? healthQuery.data ?? null;
  const metricHistory = metricHistoryQuery.data ?? [];

  const isFetching =
    deviceQuery.isFetching ||
    latestMetricsQuery.isFetching ||
    metricHistoryQuery.isFetching ||
    healthQuery.isFetching ||
    summaryQuery.isFetching;

  const error =
    deviceQuery.error ??
    latestMetricsQuery.error ??
    metricHistoryQuery.error ??
    healthQuery.error ??
    summaryQuery.error ??
    null;

  const errorMessage =
    error instanceof Error
      ? error.message
      : error
        ? "Unknown error while loading device details."
        : null;

  async function refreshDeviceData() {
    await Promise.all([
      deviceQuery.refetch(),
      latestMetricsQuery.refetch(),
      metricHistoryQuery.refetch(),
      healthQuery.refetch(),
      summaryQuery.refetch(),
    ]);
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6">
          <Link
            to="/devices"
            className="text-sm font-semibold text-slate-600 transition hover:text-slate-950"
          >
            ← Back to devices
          </Link>
        </div>

        <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">
              Device Detail
            </p>

            <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center">
              <h1 className="text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
                {device?.hostname ?? "Loading device..."}
              </h1>

              <Badge tone={getStatusTone(device?.status ?? "unknown")}>
                {device?.status ?? "unknown"}
              </Badge>
            </div>

            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
              Device ID: <span className="font-medium">{deviceId}</span>
            </p>
          </div>

          <button
            type="button"
            onClick={refreshDeviceData}
            className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isFetching}
          >
            {isFetching ? "Refreshing..." : "Refresh device"}
          </button>
        </header>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            <p className="font-semibold">Could not load device details.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <section className="mb-8 grid gap-4 lg:grid-cols-4">
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-medium text-slate-500">IP Address</p>
            <p className="mt-3 text-xl font-bold text-slate-950">
              {device?.ip_address ?? "Unknown"}
            </p>
          </article>

          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-medium text-slate-500">Operating System</p>
            <p className="mt-3 text-xl font-bold text-slate-950">
              {device?.os_name ?? "Unknown"}
            </p>
          </article>

          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-medium text-slate-500">Last Seen</p>
            <p className="mt-3 text-xl font-bold text-slate-950">
              {formatDate(device?.last_seen ?? device?.updated_at)}
            </p>
          </article>

          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-medium text-slate-500">Metric Records</p>
            <p className="mt-3 text-xl font-bold text-slate-950">
              {metricHistory.length}
            </p>
          </article>
        </section>

        <section className="mb-8 grid gap-4 xl:grid-cols-3">
          <MetricCard
            title="CPU Usage"
            value={latestMetrics?.cpu_percent}
            description="Latest processor utilisation reported by the agent."
          />

          <MetricCard
            title="Memory Usage"
            value={latestMetrics?.memory_percent}
            description="Latest RAM utilisation reported by the agent."
          />

          <MetricCard
            title="Disk Usage"
            value={latestMetrics?.disk_percent}
            description="Latest disk utilisation reported by the agent."
          />
        </section>

        <HealthScorePanel health={health} latestMetrics={latestMetrics} />

        <MetricsHistoryTable metrics={metricHistory} />
      </section>
    </main>
  );
}