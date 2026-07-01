import { useMemo, useState } from "react";
import { Link } from "react-router";
import { Badge } from "./Badge";
import { useAlertsQuery } from "../hooks/useAlertsQuery";
import { useDeviceMetricHistoryQuery } from "../hooks/useDeviceMetricHistoryQuery";
import { useDevicesQuery } from "../hooks/useDevicesQuery";
import type { Device } from "../types/api";
import { deriveMetricAnomalies } from "../utils/anomalies";
import { formatDate, formatLabel } from "../utils/format";

function getDeviceId(device: Device) {
  return device.id ?? device.device_id ?? "";
}

function getSeverityTone(severity: "warning" | "critical") {
  return severity === "critical" ? "red" : "amber";
}

export function AnomalyCentre() {
  const devicesQuery = useDevicesQuery();
  const alertsQuery = useAlertsQuery();

  const firstDeviceId = devicesQuery.data?.[0]
    ? getDeviceId(devicesQuery.data[0])
    : "";

  const [selectedDeviceId, setSelectedDeviceId] = useState("");

  const activeDeviceId = selectedDeviceId || firstDeviceId;

  const metricHistoryQuery = useDeviceMetricHistoryQuery(activeDeviceId, 200);

  const anomalies = useMemo(
    () => deriveMetricAnomalies(activeDeviceId, metricHistoryQuery.data ?? []),
    [activeDeviceId, metricHistoryQuery.data],
  );

  const selectedDevice = devicesQuery.data?.find(
    (device) => getDeviceId(device) === activeDeviceId,
  );

  const deviceAlerts = (alertsQuery.data ?? []).filter(
    (alert) => alert.device_id === activeDeviceId,
  );

  const criticalAnomalies = anomalies.filter(
    (anomaly) => anomaly.severity === "critical",
  );

  const warningAnomalies = anomalies.filter(
    (anomaly) => anomaly.severity === "warning",
  );

  async function refreshAll() {
    await Promise.all([
      devicesQuery.refetch(),
      alertsQuery.refetch(),
      metricHistoryQuery.refetch(),
    ]);
  }

  return (
    <>
      <section className="sx-panel rounded-2xl p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-50">
              Anomaly Investigation
            </h2>

            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
              Derived anomaly centre based on telemetry thresholds and alert
              correlation. This is frontend-derived from current backend metrics
              and alert data.
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-[260px_140px]">
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

            <button
              type="button"
              onClick={refreshAll}
              className="sx-button-primary mt-6 rounded-xl px-4 py-2 text-sm font-semibold"
            >
              Refresh
            </button>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <Badge tone="blue">{selectedDevice?.hostname ?? "No device"}</Badge>
          <Badge tone="red">{criticalAnomalies.length} critical</Badge>
          <Badge tone="amber">{warningAnomalies.length} warning</Badge>
          <Badge tone="slate">{deviceAlerts.length} linked alerts</Badge>
        </div>
      </section>

      <section className="mt-8 grid gap-4 lg:grid-cols-3">
        <article className="sx-panel rounded-2xl p-5">
          <p className="text-sm font-semibold text-slate-400">
            Derived Anomalies
          </p>
          <p className="mt-3 text-4xl font-bold text-slate-50">
            {anomalies.length}
          </p>
        </article>

        <article className="sx-panel rounded-2xl p-5">
          <p className="text-sm font-semibold text-slate-400">
            Critical Signals
          </p>
          <p className="mt-3 text-4xl font-bold text-rose-300">
            {criticalAnomalies.length}
          </p>
        </article>

        <article className="sx-panel rounded-2xl p-5">
          <p className="text-sm font-semibold text-slate-400">
            Alert Correlations
          </p>
          <p className="mt-3 text-4xl font-bold text-violet-300">
            {deviceAlerts.length}
          </p>
        </article>
      </section>

      <section className="sx-panel mt-8 rounded-2xl p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-50">
              Anomaly Feed
            </h2>

            <p className="mt-1 text-sm text-slate-400">
              Threshold-derived events from recent metric history.
            </p>
          </div>

          <Link
            to={`/devices/${encodeURIComponent(activeDeviceId)}`}
            className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold"
          >
            Open device
          </Link>
        </div>

        {anomalies.length === 0 ? (
          <div className="mt-6 rounded-xl border border-white/[0.056] bg-black/25 p-6 text-sm text-slate-400">
            No threshold anomalies detected for this device.
          </div>
        ) : (
          <div className="mt-6 space-y-4">
            {anomalies.slice(0, 30).map((anomaly) => (
              <article
                key={anomaly.id}
                className="rounded-2xl border border-white/[0.056] bg-black/25 p-4"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap gap-2">
                      <Badge tone={getSeverityTone(anomaly.severity)}>
                        {anomaly.severity}
                      </Badge>

                      <Badge tone="slate">
                        {formatLabel(anomaly.metric_type)}
                      </Badge>
                    </div>

                    <h3 className="mt-3 font-bold text-slate-50">
                      {anomaly.title}
                    </h3>

                    <p className="mt-2 text-sm leading-6 text-slate-300">
                      {anomaly.message}
                    </p>

                    <p className="mt-2 text-xs text-slate-500">
                      {formatDate(anomaly.created_at)}
                    </p>
                  </div>

                  <p className="text-2xl font-bold text-slate-50">
                    {anomaly.value.toFixed(1)}%
                  </p>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="sx-panel mt-8 rounded-2xl p-5">
        <h2 className="text-lg font-bold text-slate-50">Linked Alerts</h2>

        {deviceAlerts.length === 0 ? (
          <p className="mt-4 text-sm text-slate-400">
            No backend alerts are currently linked to this device.
          </p>
        ) : (
          <div className="mt-5 space-y-3">
            {deviceAlerts.slice(0, 10).map((alert, index) => (
              <article
                key={alert.id ?? alert.alert_id ?? index}
                className="rounded-xl border border-white/[0.056] bg-black/25 p-4"
              >
                <div className="flex flex-wrap gap-2">
                  <Badge
                    tone={
                      alert.severity.toLowerCase() === "critical"
                        ? "red"
                        : "amber"
                    }
                  >
                    {alert.severity}
                  </Badge>

                  <Badge tone={(alert.resolved ?? alert.is_resolved) ? "green" : "red"}>
                    {(alert.resolved ?? alert.is_resolved) ? "resolved" : "unresolved"}
                  </Badge>
                </div>

                <p className="mt-3 text-sm leading-6 text-slate-300">
                  {alert.message}
                </p>
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}