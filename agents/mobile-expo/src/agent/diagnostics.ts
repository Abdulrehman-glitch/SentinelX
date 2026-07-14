import * as Network from "expo-network";
import * as Notifications from "expo-notifications";

import { getLastRequestMeta } from "@/api/client";
import { sentinelxApi } from "@/api/endpoints";
import { getBaseUrlSync, isSecureUrl } from "@/lib/config";
import { toAppError } from "@/lib/errors";
import { collectDeviceSnapshot, heartbeatMessage } from "./deviceInfo";
import { loadEnrolment } from "./identity";

// §7 — on-demand diagnostic run. Each check is independent and reports
// pass / warn / fail with a short human-readable detail line.

export type CheckOutcome = "pass" | "warn" | "fail" | "skipped";

export interface DiagnosticResult {
  id: string;
  label: string;
  outcome: CheckOutcome;
  detail: string;
}

export interface DiagnosticReport {
  startedAt: string;
  finishedAt: string;
  baseUrl: string;
  results: DiagnosticResult[];
}

export async function runDiagnostics(): Promise<DiagnosticReport> {
  const startedAt = new Date().toISOString();
  const results: DiagnosticResult[] = [];

  // 1. Device connectivity
  const network = await Network.getNetworkStateAsync().catch(() => null);
  results.push({
    id: "connectivity",
    label: "Network connectivity",
    outcome: network?.isConnected ? "pass" : "fail",
    detail: network?.isConnected
      ? `Connected via ${network.type?.toLowerCase() ?? "unknown"}`
      : "No network connection detected",
  });

  // 2. Transport security
  const baseUrl = getBaseUrlSync();
  results.push({
    id: "https",
    label: "Transport security",
    outcome: isSecureUrl(baseUrl) ? "pass" : "warn",
    detail: isSecureUrl(baseUrl)
      ? "API URL uses HTTPS"
      : "API URL uses plain HTTP — acceptable for local development only",
  });

  // 3. Backend health + DNS/handshake (implicit in a successful fetch) + latency
  let clockSkewMs: number | null = null;
  try {
    await sentinelxApi.health();
    const meta = getLastRequestMeta();
    results.push({
      id: "backend",
      label: "Backend health endpoint",
      outcome: "pass",
      detail: `Reachable in ${meta?.latencyMs ?? "?"} ms`,
    });
    if (meta?.serverDate) {
      clockSkewMs = Date.parse(meta.serverDate) - Date.now();
    }
  } catch (err) {
    const appErr = toAppError(err);
    results.push({
      id: "backend",
      label: "Backend health endpoint",
      outcome: "fail",
      detail: `${appErr.title} (ref ${appErr.reference})`,
    });
  }

  // 4. Clock difference between client and server
  if (clockSkewMs != null) {
    const abs = Math.abs(clockSkewMs);
    results.push({
      id: "clock",
      label: "Clock alignment",
      outcome: abs < 90_000 ? "pass" : "warn",
      detail: `Device is ${(clockSkewMs / 1000).toFixed(0)}s ${clockSkewMs >= 0 ? "behind" : "ahead of"} the server`,
    });
  } else {
    results.push({ id: "clock", label: "Clock alignment", outcome: "skipped", detail: "No server timestamp available" });
  }

  // 5. User authentication
  try {
    const me = await sentinelxApi.me();
    results.push({
      id: "auth",
      label: "API authentication",
      outcome: "pass",
      detail: `Signed in as ${me.email} (${me.role})`,
    });
  } catch (err) {
    const appErr = toAppError(err);
    results.push({
      id: "auth",
      label: "API authentication",
      outcome: "fail",
      detail: `${appErr.title} (ref ${appErr.reference})`,
    });
  }

  // 6. Agent upload test (real heartbeat when enrolled)
  const enrolment = await loadEnrolment();
  if (enrolment) {
    try {
      const snapshot = await collectDeviceSnapshot();
      await sentinelxApi.sendHeartbeat(
        { device_id: enrolment.deviceId, status: "online", message: `diagnostic · ${heartbeatMessage(snapshot)}` },
        enrolment.deviceToken,
      );
      results.push({ id: "upload", label: "Agent upload test", outcome: "pass", detail: "Heartbeat accepted" });
    } catch (err) {
      const appErr = toAppError(err);
      results.push({
        id: "upload",
        label: "Agent upload test",
        outcome: "fail",
        detail: `${appErr.title} (ref ${appErr.reference})`,
      });
    }
  } else {
    results.push({ id: "upload", label: "Agent upload test", outcome: "skipped", detail: "Agent not enrolled" });
  }

  // 7. Notification permission
  const notif = await Notifications.getPermissionsAsync().catch(() => null);
  results.push({
    id: "notifications",
    label: "Notification permission",
    outcome: notif?.status === "granted" ? "pass" : "warn",
    detail: notif?.status === "granted" ? "Notifications allowed" : `Status: ${notif?.status ?? "unknown"}`,
  });

  return { startedAt, finishedAt: new Date().toISOString(), baseUrl, results };
}

export function formatReport(report: DiagnosticReport): string {
  const lines = [
    `SentinelX Mobile diagnostic report`,
    `Run: ${report.startedAt}`,
    `API: ${report.baseUrl}`,
    "",
    ...report.results.map((r) => `[${r.outcome.toUpperCase()}] ${r.label} — ${r.detail}`),
  ];
  return lines.join("\n");
}
