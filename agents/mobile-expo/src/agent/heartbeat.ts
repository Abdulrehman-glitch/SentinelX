import * as Crypto from "expo-crypto";
import * as Network from "expo-network";
import { AppState, AppStateStatus } from "react-native";

import { sentinelxApi } from "@/api/endpoints";
import { getLastRequestMeta } from "@/api/client";
import { backoffDelay, isRetryableStatus } from "@/lib/backoff";
import { isAppError } from "@/lib/errors";
import { collectDeviceSnapshot, heartbeatMessage } from "./deviceInfo";
import { loadEnrolment } from "./identity";
import { enqueue, loadQueue, markAttempt, QueuedHeartbeat, removeSent, saveQueue } from "./queue";

// §8/§9 — the agent only reports while the app is active. iOS decides when
// background work runs, so no timers pretend otherwise; unsent heartbeats are
// queued and flushed on foreground / reconnect.

export interface AgentStatus {
  running: boolean;
  lastSyncAt: number | null;
  lastAttemptAt: number | null;
  lastLatencyMs: number | null;
  lastError: string | null;
  queueLength: number;
  consecutiveFailures: number;
  credentialInvalid: boolean;
}

type Listener = (status: AgentStatus) => void;

const HEARTBEAT_INTERVAL_MS = 60_000;

class AgentRuntime {
  private status: AgentStatus = {
    running: false,
    lastSyncAt: null,
    lastAttemptAt: null,
    lastLatencyMs: null,
    lastError: null,
    queueLength: 0,
    consecutiveFailures: 0,
    credentialInvalid: false,
  };

  private listeners = new Set<Listener>();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private appStateSub: { remove(): void } | null = null;
  private networkSub: { remove(): void } | null = null;
  private sending = false;

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    listener(this.status);
    return () => this.listeners.delete(listener);
  }

  getStatus(): AgentStatus {
    return this.status;
  }

  private emit(patch: Partial<AgentStatus>) {
    this.status = { ...this.status, ...patch };
    this.listeners.forEach((fn) => fn(this.status));
  }

  async start(): Promise<void> {
    if (this.status.running) return;
    const enrolment = await loadEnrolment();
    if (!enrolment) return;

    this.emit({ running: true, credentialInvalid: false });

    this.appStateSub = AppState.addEventListener("change", (next: AppStateStatus) => {
      if (next === "active") {
        void this.tick("foreground");
      } else {
        // Complete gracefully on backgrounding: stop the timer, keep the queue.
        this.clearTimer();
      }
    });

    // §8 — send after network reconnection.
    this.networkSub = Network.addNetworkStateListener((state) => {
      if (state.isConnected && this.status.queueLength > 0) {
        void this.tick("reconnect");
      }
    });

    await this.refreshQueueLength();
    void this.tick("start");
  }

  stop(): void {
    this.clearTimer();
    this.appStateSub?.remove();
    this.appStateSub = null;
    this.networkSub?.remove();
    this.networkSub = null;
    this.emit({ running: false });
  }

  async sendNow(): Promise<boolean> {
    return this.tick("manual");
  }

  private clearTimer() {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  private scheduleNext(delayMs: number) {
    this.clearTimer();
    if (!this.status.running) return;
    if (AppState.currentState !== "active") return;
    this.timer = setTimeout(() => void this.tick("interval"), delayMs);
  }

  private async refreshQueueLength() {
    const queue = await loadQueue();
    this.emit({ queueLength: queue.length });
  }

  private async tick(_reason: string): Promise<boolean> {
    if (this.sending || !this.status.running) return false;
    this.sending = true;
    try {
      const enrolment = await loadEnrolment();
      if (!enrolment) {
        this.stop();
        return false;
      }

      const snapshot = await collectDeviceSnapshot();
      const fresh: QueuedHeartbeat = {
        clientId: Crypto.randomUUID(),
        status: "online",
        message: heartbeatMessage(snapshot),
        queuedAt: new Date().toISOString(),
        attempts: 0,
      };

      let queue = enqueue(await loadQueue(), fresh);
      await saveQueue(queue);
      this.emit({ queueLength: queue.length, lastAttemptAt: Date.now() });

      if (!snapshot.isConnected) {
        this.emit({ lastError: "offline" });
        this.scheduleNext(HEARTBEAT_INTERVAL_MS);
        return false;
      }

      // Flush oldest-first so ordering is preserved server-side.
      const sentIds: string[] = [];
      for (const entry of queue) {
        queue = markAttempt(queue, entry.clientId);
        try {
          await sentinelxApi.sendHeartbeat(
            { device_id: enrolment.deviceId, status: entry.status, message: entry.message },
            enrolment.deviceToken,
          );
          sentIds.push(entry.clientId);
        } catch (err) {
          const status = isAppError(err) ? err.status : undefined;
          if (isAppError(err) && err.kind === "device_token_invalid") {
            // §8 — never retry auth failures.
            this.emit({ credentialInvalid: true, lastError: err.title });
            this.clearTimer();
            break;
          }
          if (!isRetryableStatus(status)) {
            // Permanently rejected (validation etc.) — drop it, don't wedge the queue.
            sentIds.push(entry.clientId);
          }
          break;
        }
      }

      queue = removeSent(queue, sentIds);
      await saveQueue(queue);

      if (sentIds.length > 0) {
        this.emit({
          lastSyncAt: Date.now(),
          lastLatencyMs: getLastRequestMeta()?.latencyMs ?? null,
        });
      }

      if (queue.length === 0) {
        this.emit({ queueLength: 0, lastError: null, consecutiveFailures: 0 });
        this.scheduleNext(HEARTBEAT_INTERVAL_MS);
        return true;
      }

      const failures = this.status.consecutiveFailures + 1;
      this.emit({
        queueLength: queue.length,
        consecutiveFailures: failures,
        lastError: this.status.credentialInvalid ? this.status.lastError : "send failed — will retry",
      });
      if (!this.status.credentialInvalid) {
        this.scheduleNext(backoffDelay(failures));
      }
      return false;
    } finally {
      this.sending = false;
    }
  }
}

export const agentRuntime = new AgentRuntime();
