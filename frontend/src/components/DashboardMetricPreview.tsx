import { Link } from "react-router";
import { MetricHistoryChart } from "./MetricHistoryChart";
import { MetricUsageBars } from "./MetricUsageBars";
import type { Device, SystemMetric } from "../types/api";

type DashboardMetricPreviewProps = {
  device?: Device | null;
  latestMetrics?: SystemMetric | null;
  metricHistory: SystemMetric[];
};

function getDeviceId(device?: Device | null) {
  return device?.id ?? device?.device_id ?? "";
}

export function DashboardMetricPreview({
  device,
  latestMetrics,
  metricHistory,
}: DashboardMetricPreviewProps) {
  const deviceId = getDeviceId(device);

  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">
            Telemetry Preview
          </p>

          <h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-950">
            {device?.hostname ?? "No device selected"}
          </h2>

          <p className="mt-2 text-sm leading-6 text-slate-600">
            Live metric preview for the first available registered device.
          </p>
        </div>

        {deviceId && (
          <Link
            to={`/devices/${encodeURIComponent(deviceId)}`}
            className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
          >
            Open device detail
          </Link>
        )}
      </div>

      {!deviceId ? (
        <div className="mt-6 rounded-xl bg-slate-50 p-6 text-sm text-slate-500">
          Register a device to show live telemetry preview.
        </div>
      ) : (
        <div className="mt-6 grid gap-6 xl:grid-cols-[360px_1fr]">
          <MetricUsageBars latestMetrics={latestMetrics} />

          <div className="-mt-8">
            <MetricHistoryChart metrics={metricHistory.slice(-30)} />
          </div>
        </div>
      )}
    </section>
  );
}