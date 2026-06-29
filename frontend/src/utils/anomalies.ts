import type { Alert, Device, SystemMetric } from "../types/api";
import { formatLabel } from "./format";
import { getMetricTimestamp, sortMetricsOldestFirst } from "./metrics";

export type DerivedAnomaly = {
  id: string;
  device_id: string;
  title: string;
  metric_type: "cpu_percent" | "memory_percent" | "disk_percent";
  severity: "warning" | "critical";
  value: number;
  message: string;
  created_at: string;
};

function getDeviceId(device: Device) {
  return device.id ?? device.device_id ?? "";
}

function getSeverity(value: number) {
  if (value >= 90) {
    return "critical" as const;
  }

  if (value >= 75) {
    return "warning" as const;
  }

  return null;
}

function buildMetricAnomaly(
  deviceId: string,
  metric: SystemMetric,
  metricType: "cpu_percent" | "memory_percent" | "disk_percent",
): DerivedAnomaly | null {
  const value = metric[metricType];
  const severity = getSeverity(value);

  if (!severity) {
    return null;
  }

  return {
    id: `${deviceId}-${metricType}-${getMetricTimestamp(metric)}-${value}`,
    device_id: deviceId,
    title: `${formatLabel(metricType)} anomaly`,
    metric_type: metricType,
    severity,
    value,
    message: `${formatLabel(metricType)} reached ${value.toFixed(
      1,
    )}%, which crosses the ${severity} threshold.`,
    created_at: getMetricTimestamp(metric),
  };
}

export function deriveMetricAnomalies(
  deviceId: string,
  metrics: SystemMetric[],
): DerivedAnomaly[] {
  const sortedMetrics = sortMetricsOldestFirst(metrics);

  return sortedMetrics
    .flatMap((metric) => [
      buildMetricAnomaly(deviceId, metric, "cpu_percent"),
      buildMetricAnomaly(deviceId, metric, "memory_percent"),
      buildMetricAnomaly(deviceId, metric, "disk_percent"),
    ])
    .filter((anomaly): anomaly is DerivedAnomaly => Boolean(anomaly))
    .sort((a, b) => {
      const aDate = new Date(a.created_at).getTime();
      const bDate = new Date(b.created_at).getTime();

      return (Number.isNaN(bDate) ? 0 : bDate) - (Number.isNaN(aDate) ? 0 : aDate);
    });
}

export function getDeviceRiskLevel(
  device: Device,
  alerts: Alert[],
  anomalies: DerivedAnomaly[] = [],
) {
  const deviceId = getDeviceId(device);

  const deviceAlerts = alerts.filter((alert) => alert.device_id === deviceId);
  const unresolvedCriticalAlerts = deviceAlerts.filter((alert) => {
    const resolved = alert.resolved ?? alert.is_resolved ?? false;

    return !resolved && alert.severity.toLowerCase() === "critical";
  });

  const criticalAnomalies = anomalies.filter(
    (anomaly) => anomaly.device_id === deviceId && anomaly.severity === "critical",
  );

  if (device.status?.toLowerCase() === "offline") {
    return "critical" as const;
  }

  if (unresolvedCriticalAlerts.length > 0 || criticalAnomalies.length > 0) {
    return "critical" as const;
  }

  const unresolvedWarningAlerts = deviceAlerts.filter((alert) => {
    const resolved = alert.resolved ?? alert.is_resolved ?? false;

    return !resolved && alert.severity.toLowerCase() === "warning";
  });

  if (unresolvedWarningAlerts.length > 0) {
    return "warning" as const;
  }

  return "healthy" as const;
}