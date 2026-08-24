/**
 * A Server-Sent Events client built on fetch rather than EventSource.
 *
 * EventSource cannot send an Authorization header, and SentinelX's access
 * token deliberately lives in memory rather than in a cookie the browser would
 * attach on its own (see lib/authStorage.ts). The usual workarounds are worse
 * than the problem: a token in the query string ends up in access logs and
 * browser history, and a second cookie-authenticated channel would undo the
 * reason the token is held in memory at all.
 *
 * So this reads the response body as a stream and parses the handful of SSE
 * framing rules it needs. That also buys back the two things EventSource does
 * badly for this use: reconnection is under our control, so backoff can be
 * bounded and jittered, and `Last-Event-ID` is sent on the *first* request
 * after a drop rather than only after the server has already replied.
 *
 * The stream is never treated as truth. Frames say what changed; the caller
 * refetches through the normal API. A dropped connection therefore costs
 * freshness, never correctness.
 */

import { API_BASE_URL } from "./api";
import { authStorage } from "./authStorage";

export type LiveEvent = {
  id: string;
  sequence: number;
  type: string;
  device_id: string | null;
  resource_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

/**
 * connecting   - first attempt, or reconnecting after a clean server cycle.
 * live         - connected, and the server has spoken recently.
 * reconnecting - dropped, backing off, will try again.
 * stale        - still connected but nothing has arrived for longer than the
 *                server's heartbeat interval, so the connection is suspect.
 * offline      - the browser reports no network, or the server closed the
 *                stream deliberately.
 */
export type LiveStatus = "connecting" | "live" | "reconnecting" | "stale" | "offline";

export type LiveStreamHandlers = {
  onEvent: (event: LiveEvent) => void;
  onStatus: (status: LiveStatus) => void;
};

// Backoff for reconnection. Capped, because an operations console that has
// been asleep for an hour should come back promptly, not after a 30-minute
// exponential delay.
const BASE_RETRY_MS = 1_000;
const MAX_RETRY_MS = 20_000;

// The server heartbeats every 15s. Silence appreciably longer than that means
// something between here and there has stopped forwarding, even though the
// socket still looks open.
const STALE_AFTER_MS = 40_000;

function jitter(ms: number): number {
  // Spread reconnects so a backend restart does not bring every open console
  // back in the same millisecond.
  return Math.round(ms * (0.5 + Math.random() * 0.5));
}

/**
 * Splits an SSE byte stream into frames and dispatches them.
 * Returns a stop() that cancels the connection and all pending retries.
 */
export function connectLiveStream(handlers: LiveStreamHandlers): () => void {
  let stopped = false;
  let controller: AbortController | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let staleTimer: ReturnType<typeof setInterval> | null = null;
  let attempt = 0;
  let lastEventId: string | null = null;
  let lastActivityAt = Date.now();
  let status: LiveStatus = "connecting";

  function setStatus(next: LiveStatus) {
    if (status === next) return;
    status = next;
    handlers.onStatus(next);
  }

  function markActive() {
    lastActivityAt = Date.now();
    if (status === "stale") setStatus("live");
  }

  function handleFrame(raw: string) {
    // Comment frames (": heartbeat") are the server proving it is alive. They
    // carry nothing, but they do reset staleness.
    if (!raw.trim() || raw.startsWith(":")) {
      markActive();
      return;
    }

    let eventType = "message";
    let data = "";
    let id: string | null = null;

    for (const line of raw.split("\n")) {
      if (line.startsWith("event:")) eventType = line.slice(6).trim();
      else if (line.startsWith("data:")) data += line.slice(5).trim();
      else if (line.startsWith("id:")) id = line.slice(3).trim();
    }

    if (id) lastEventId = id;
    markActive();

    if (eventType === "stream.ready" || eventType === "stream.cycle") return;
    if (eventType === "stream.closed") {
      // The server ended it deliberately (revoked session). Retrying would
      // only produce a 401 loop.
      stopped = true;
      setStatus("offline");
      return;
    }
    if (!data) return;

    try {
      handlers.onEvent(JSON.parse(data) as LiveEvent);
    } catch {
      // A malformed frame must not tear down a working connection.
    }
  }

  function scheduleRetry(delayOverride?: number) {
    if (stopped) return;
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      setStatus("offline");
    } else {
      setStatus("reconnecting");
    }

    const delay = delayOverride ?? jitter(Math.min(BASE_RETRY_MS * 2 ** attempt, MAX_RETRY_MS));
    attempt += 1;
    retryTimer = setTimeout(() => void run(), delay);
  }

  async function run() {
    if (stopped) return;

    const token = authStorage.getToken();
    if (!token) {
      // Not signed in yet, or mid-refresh. Try again shortly rather than
      // opening an unauthenticated stream that could only 401.
      scheduleRetry();
      return;
    }

    controller = new AbortController();
    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
      Accept: "text/event-stream",
    };
    if (lastEventId) headers["Last-Event-ID"] = lastEventId;

    try {
      const response = await fetch(`${API_BASE_URL}/events/stream`, {
        headers,
        credentials: "include",
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        // 401 included: the API layer refreshes the token on its own
        // schedule, so back off and pick the new one up next attempt.
        scheduleRetry();
        return;
      }

      attempt = 0;
      markActive();
      setStatus("live");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Frames are separated by a blank line. Anything after the last
        // separator is a partial frame and stays in the buffer.
        let separator = buffer.indexOf("\n\n");
        while (separator !== -1) {
          handleFrame(buffer.slice(0, separator));
          buffer = buffer.slice(separator + 2);
          separator = buffer.indexOf("\n\n");
        }
      }

      // Server closed cleanly (its max-lifetime cycle). Reconnect at once
      // rather than backing off - this is expected, not a failure.
      attempt = 0;
      scheduleRetry(0);
    } catch {
      if (!stopped) scheduleRetry();
    }
  }

  staleTimer = setInterval(() => {
    if (stopped || status !== "live") return;
    if (Date.now() - lastActivityAt > STALE_AFTER_MS) setStatus("stale");
  }, 5_000);

  void run();

  return () => {
    stopped = true;
    controller?.abort();
    if (retryTimer) clearTimeout(retryTimer);
    if (staleTimer) clearInterval(staleTimer);
  };
}
