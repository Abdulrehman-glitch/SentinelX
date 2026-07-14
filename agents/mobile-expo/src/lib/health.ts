import type { StatusTone } from "@/theme/tokens";

export type HealthStatus = "healthy" | "warning" | "critical" | "unknown";

export function classifyHealthScore(score: number | null | undefined): HealthStatus {
  if (score == null || Number.isNaN(score)) return "unknown";
  if (score >= 80) return "healthy";
  if (score >= 50) return "warning";
  return "critical";
}

export function healthTone(status: string | null | undefined): StatusTone {
  switch (status) {
    case "healthy":
      return "healthy";
    case "warning":
      return "warning";
    case "critical":
      return "critical";
    default:
      return "offline";
  }
}

export function severityTone(severity: string | null | undefined): StatusTone {
  switch (severity) {
    case "critical":
      return "critical";
    case "warning":
      return "warning";
    case "info":
      return "info";
    default:
      return "offline";
  }
}

export function deviceStatusTone(status: string | null | undefined): StatusTone {
  switch (status) {
    case "online":
      return "healthy";
    case "offline":
      return "critical";
    case "disabled":
      return "offline";
    default:
      return "offline";
  }
}

// §8 — honest sync-state wording; iOS decides when background work runs.
export type SyncState =
  | "live"
  | "recently_synced"
  | "delayed"
  | "offline"
  | "unavailable"
  | "unknown";

export function classifySyncState(opts: {
  online: boolean;
  appActive: boolean;
  lastSyncAt: number | null;
  nowMs?: number;
}): SyncState {
  const now = opts.nowMs ?? Date.now();
  if (!opts.online) return "offline";
  if (opts.lastSyncAt == null) return "unknown";
  const age = now - opts.lastSyncAt;
  if (opts.appActive && age < 2 * 60_000) return "live";
  if (age < 10 * 60_000) return "recently_synced";
  return "delayed";
}

export const syncStateLabel: Record<SyncState, string> = {
  live: "Live",
  recently_synced: "Recently synced",
  delayed: "Sync delayed",
  offline: "Offline",
  unavailable: "Background sync unavailable",
  unknown: "Unknown",
};
