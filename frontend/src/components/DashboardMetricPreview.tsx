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
    <section className="sx-panel mt-8 rounded-2xl p-5 sx-animate-in sx-delay-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.25em] sx-c-text0">
            Telemetry Preview
          </p>

          <h2 className="mt-2 text-2xl font-bold tracking-tight sx-c-text">
            {device?.hostname ?? "No device selected"}
          </h2>

          <p className="mt-2 text-sm leading-6 sx-c-muted">
            Live metric preview for the first available registered device.
          </p>
        </div>

        {deviceId && (
          <Link
            to={`/devices/${encodeURIComponent(deviceId)}`}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold"
          >
            Open device detail
          </Link>
        )}
      </div>

      {!deviceId ? (
        <div className="mt-6 rounded-xl border border-slate-700/50 sx-c-surface p-6 text-sm sx-c-muted">
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
