import type { Alert, Incident, RecoveryAction } from "../types/api";
import { formatLabel } from "./format";

export type SentinelNotification = {
  id: string;
  title: string;
  message: string;
  source: "alert" | "incident" | "recovery";
  severity: "info" | "warning" | "critical" | "success";
  status: string;
  created_at: string;
  href: string;
};

function isAlertResolved(alert: Alert) {
  return alert.resolved ?? alert.is_resolved ?? false;
}

function getAlertId(alert: Alert, index: number) {
  return alert.id ?? alert.alert_id ?? `alert-${index}`;
}

function getRecoveryId(action: RecoveryAction, index: number) {
  return action.id ?? action.recovery_action_id ?? `recovery-${index}`;
}

export function buildNotifications(
  alerts: Alert[],
  incidents: Incident[],
  recoveryActions: RecoveryAction[],
): SentinelNotification[] {
  const alertNotifications: SentinelNotification[] = alerts.map((alert, index) => {
    const resolved = isAlertResolved(alert);

    return {
      id: `alert-${getAlertId(alert, index)}`,
      title: `${formatLabel(alert.alert_type ?? alert.metric_type ?? "system")} alert`,
      message: alert.message,
      source: "alert",
      severity:
        alert.severity.toLowerCase() === "critical" ? "critical" : "warning",
      status: resolved ? "resolved" : "unresolved",
      created_at: alert.created_at ?? "",
      href: "/alerts",
    };
  });

  const incidentNotifications: SentinelNotification[] = incidents.map(
    (incident) => ({
      id: `incident-${incident.id}`,
      title: incident.title,
      message:
        incident.description ??
        `Incident status is currently ${incident.status}.`,
      source: "incident",
      severity:
        incident.severity.toLowerCase() === "critical"
          ? "critical"
          : "warning",
      status: incident.status,
      created_at: incident.created_at,
      href: `/incidents/${encodeURIComponent(incident.id)}`,
    }),
  );

  const recoveryNotifications: SentinelNotification[] = recoveryActions.map(
    (action, index) => ({
      id: `recovery-${getRecoveryId(action, index)}`,
      title: `${formatLabel(action.action_type)} logged`,
      message: action.details ?? "Recovery action logged for traceability.",
      source: "recovery",
      severity: action.status.toLowerCase() === "failed" ? "critical" : "success",
      status: action.status,
      created_at: action.created_at ?? "",
      href: "/recovery-actions",
    }),
  );

  return [
    ...alertNotifications,
    ...incidentNotifications,
    ...recoveryNotifications,
  ].sort((a, b) => {
    const aDate = new Date(a.created_at).getTime();
    const bDate = new Date(b.created_at).getTime();

    return (Number.isNaN(bDate) ? 0 : bDate) - (Number.isNaN(aDate) ? 0 : aDate);
  });
}