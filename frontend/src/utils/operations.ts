import type {
  Alert,
  Device,
  OverviewResponse,
  RecoveryAction,
} from "../types/api";

export function isAlertResolved(alert: Alert) {
  return alert.resolved ?? alert.is_resolved ?? false;
}

export function getDeviceId(device: Device) {
  return device.id ?? device.device_id ?? "";
}

export function getAlertId(alert: Alert) {
  return alert.id ?? alert.alert_id ?? "";
}

export function getAlertType(alert: Alert) {
  return alert.alert_type ?? alert.metric_type ?? "system";
}

export function getOnlineDeviceCount(
  overview: OverviewResponse | null,
  devices: Device[],
) {
  if (typeof overview?.devices.online === "number") {
    return overview.devices.online;
  }

  return devices.filter((device) => device.status?.toLowerCase() === "online")
    .length;
}

export function getOfflineDeviceCount(
  overview: OverviewResponse | null,
  devices: Device[],
) {
  if (typeof overview?.devices.offline === "number") {
    return overview.devices.offline;
  }

  return devices.filter((device) => device.status?.toLowerCase() === "offline")
    .length;
}

export function getTotalDeviceCount(
  overview: OverviewResponse | null,
  devices: Device[],
) {
  if (typeof overview?.devices.total === "number") {
    return overview.devices.total;
  }

  return devices.length;
}

export function getOpenAlerts(alerts: Alert[]) {
  return alerts.filter((alert) => !isAlertResolved(alert));
}

export function getCriticalOpenAlerts(alerts: Alert[]) {
  return getOpenAlerts(alerts).filter(
    (alert) => alert.severity.toLowerCase() === "critical",
  );
}

export function getWarningOpenAlerts(alerts: Alert[]) {
  return getOpenAlerts(alerts).filter(
    (alert) => alert.severity.toLowerCase() === "warning",
  );
}

export function getFleetAvailabilityPercent(
  overview: OverviewResponse | null,
  devices: Device[],
) {
  const total = getTotalDeviceCount(overview, devices);
  const online = getOnlineDeviceCount(overview, devices);

  if (total === 0) {
    return 0;
  }

  return Math.round((online / total) * 100);
}

export function getOperationalPosture(
  overview: OverviewResponse | null,
  devices: Device[],
  alerts: Alert[],
) {
  const criticalAlerts = getCriticalOpenAlerts(alerts).length;
  const warningAlerts = getWarningOpenAlerts(alerts).length;
  const offlineDevices = getOfflineDeviceCount(overview, devices);

  if (criticalAlerts > 0 || offlineDevices > 0) {
    return {
      label: "Critical attention required",
      tone: "red" as const,
      description:
        "One or more devices or alerts require immediate operational review.",
    };
  }

  if (warningAlerts > 0) {
    return {
      label: "Warning conditions present",
      tone: "amber" as const,
      description:
        "The platform is operational, but warning alerts should be reviewed.",
    };
  }

  return {
    label: "Operationally stable",
    tone: "green" as const,
    description:
      "No unresolved critical or warning conditions are currently active.",
  };
}

export function sortAlertsForOperations(alerts: Alert[]) {
  return [...alerts].sort((a, b) => {
    const aResolved = isAlertResolved(a);
    const bResolved = isAlertResolved(b);

    if (aResolved !== bResolved) {
      return aResolved ? 1 : -1;
    }

    const severityWeight = {
      critical: 3,
      warning: 2,
      info: 1,
    };

    const aWeight =
      severityWeight[a.severity.toLowerCase() as keyof typeof severityWeight] ??
      0;

    const bWeight =
      severityWeight[b.severity.toLowerCase() as keyof typeof severityWeight] ??
      0;

    if (aWeight !== bWeight) {
      return bWeight - aWeight;
    }

    const aDate = new Date(a.created_at ?? "").getTime();
    const bDate = new Date(b.created_at ?? "").getTime();

    return (Number.isNaN(bDate) ? 0 : bDate) - (Number.isNaN(aDate) ? 0 : aDate);
  });
}

export function sortRecoveryActionsByNewest(actions: RecoveryAction[]) {
  return [...actions].sort((a, b) => {
    const aDate = new Date(a.created_at ?? "").getTime();
    const bDate = new Date(b.created_at ?? "").getTime();

    return (Number.isNaN(bDate) ? 0 : bDate) - (Number.isNaN(aDate) ? 0 : aDate);
  });
}