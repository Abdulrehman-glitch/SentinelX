import type { Alert, AuditLog, RecoveryAction } from "../types/api";
import { formatLabel } from "./format";
import { getAlertId, getAlertType, isAlertResolved } from "./operations";

export type StreamEventKind = "alert" | "recovery" | "audit";
export type StreamEventSeverity = "critical" | "warning" | "info" | "resolved";

export type StreamEvent = {
  key: string;
  kind: StreamEventKind;
  severity: StreamEventSeverity;
  headline: string;
  detail: string;
  timestamp: string;
  href: string;
};

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(ms) || ms < 0) return "—";
  if (ms < 60_000) return "now";
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h`;
  return `${Math.floor(ms / 86_400_000)}d`;
}

function mapAlert(alert: Alert, i: number): StreamEvent {
  const id = getAlertId(alert) || String(i);
  const resolved = isAlertResolved(alert);
  const sev = alert.severity?.toLowerCase();
  return {
    key: `alert-${id}`,
    kind: "alert",
    severity: resolved
      ? "resolved"
      : sev === "critical"
        ? "critical"
        : sev === "warning"
          ? "warning"
          : "info",
    headline: formatLabel(getAlertType(alert)),
    detail: alert.message ?? "Alert generated",
    timestamp: alert.created_at ?? "",
    href: "/alerts",
  };
}

function mapRecovery(action: RecoveryAction, i: number): StreamEvent {
  return {
    key: `recovery-${action.id ?? action.recovery_action_id ?? i}`,
    kind: "recovery",
    severity: "info",
    headline: formatLabel(action.action_type),
    detail: action.details ?? "Recovery action logged",
    timestamp: action.created_at ?? "",
    href: "/recovery-actions",
  };
}

function mapAuditLog(log: AuditLog, i: number): StreamEvent {
  const sev = log.severity?.toLowerCase();
  return {
    key: `audit-${log.id}-${i}`,
    kind: "audit",
    severity:
      sev === "critical" ? "critical" : sev === "warning" ? "warning" : "info",
    headline: formatLabel(log.action),
    detail: log.message ?? "",
    timestamp: log.created_at ?? "",
    href: "/audit-logs",
  };
}

export function buildEventStream(
  alerts: Alert[],
  recoveryActions: RecoveryAction[],
  auditLogs: AuditLog[],
  limit = 48,
): StreamEvent[] {
  const all: StreamEvent[] = [
    ...alerts.map(mapAlert),
    ...recoveryActions.map(mapRecovery),
    ...auditLogs.slice(0, 30).map(mapAuditLog),
  ];

  return all
    .filter((e) => !!e.timestamp)
    .sort((a, b) => {
      const at = new Date(a.timestamp).getTime();
      const bt = new Date(b.timestamp).getTime();
      return (Number.isNaN(bt) ? 0 : bt) - (Number.isNaN(at) ? 0 : at);
    })
    .slice(0, limit);
}
