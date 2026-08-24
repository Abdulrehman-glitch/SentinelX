/**
 * The SSE client's job is to be boring under bad conditions: partial frames,
 * garbage payloads, a server that hangs up, a token that is not there yet.
 * None of those may lose an event or spin the browser.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../authStorage";
import { connectLiveStream, type LiveEvent, type LiveStatus } from "../liveStream";

function sseBody(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index >= chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(chunks[index++]));
    },
  });
}

function frame(type: string, body: Partial<LiveEvent>, sequence = 1): string {
  return (
    `id: ${sequence}\n` +
    `event: ${type}\n` +
    `data: ${JSON.stringify({
      id: `evt-${sequence}`,
      sequence,
      type,
      device_id: null,
      resource_id: null,
      payload: {},
      created_at: "2026-08-24T12:00:00+00:00",
      ...body,
    })}\n\n`
  );
}

function collect() {
  const events: LiveEvent[] = [];
  const statuses: LiveStatus[] = [];
  return {
    events,
    statuses,
    handlers: {
      onEvent: (e: LiveEvent) => events.push(e),
      onStatus: (s: LiveStatus) => statuses.push(s),
    },
  };
}

/** Lets the stream's promise chain drain without depending on wall-clock time. */
async function settle(times = 12) {
  for (let i = 0; i < times; i += 1) await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
}

describe("connectLiveStream", () => {
  beforeEach(() => {
    authStorage.setToken("test-token", 900);
  });

  afterEach(() => {
    authStorage.clearToken();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("parses complete frames into events", async () => {
    const { events, handlers } = collect();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: sseBody([frame("alert.created", { payload: { severity: "critical" } }, 7)]),
      }),
    );

    const stop = connectLiveStream(handlers);
    await settle();
    stop();

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("alert.created");
    expect(events[0].payload).toEqual({ severity: "critical" });
  });

  it("reassembles a frame split across network chunks", async () => {
    const { events, handlers } = collect();
    const whole = frame("incident.created", {}, 3);
    const split = Math.floor(whole.length / 2);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: sseBody([whole.slice(0, split), whole.slice(split)]),
      }),
    );

    const stop = connectLiveStream(handlers);
    await settle();
    stop();

    expect(events.map((e) => e.type)).toEqual(["incident.created"]);
  });

  it("delivers several frames arriving in one chunk", async () => {
    const { events, handlers } = collect();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: sseBody([frame("alert.created", {}, 1) + frame("alert.updated", {}, 2)]),
      }),
    );

    const stop = connectLiveStream(handlers);
    await settle();
    stop();

    expect(events.map((e) => e.sequence)).toEqual([1, 2]);
  });

  it("ignores heartbeat comments without emitting an event", async () => {
    const { events, statuses, handlers } = collect();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: sseBody([": heartbeat\n\n", frame("alert.created", {}, 1)]),
      }),
    );

    const stop = connectLiveStream(handlers);
    await settle();
    stop();

    expect(events).toHaveLength(1);
    expect(statuses).toContain("live");
  });

  it("survives a malformed payload instead of tearing down", async () => {
    const { events, handlers } = collect();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: sseBody([
          "event: alert.created\ndata: {not json\n\n",
          frame("alert.updated", {}, 2),
        ]),
      }),
    );

    const stop = connectLiveStream(handlers);
    await settle();
    stop();

    expect(events.map((e) => e.type)).toEqual(["alert.updated"]);
  });

  it("does not surface the stream's own control frames as events", async () => {
    const { events, handlers } = collect();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: sseBody([
          'event: stream.ready\ndata: {"cursor":0}\n\n',
          frame("alert.created", {}, 1),
        ]),
      }),
    );

    const stop = connectLiveStream(handlers);
    await settle();
    stop();

    expect(events.map((e) => e.type)).toEqual(["alert.created"]);
  });

  it("stops retrying when the server says the session was revoked", async () => {
    const { statuses, handlers } = collect();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: sseBody(['event: stream.closed\ndata: {"reason":"session_revoked"}\n\n']),
      }),
    );

    const stop = connectLiveStream(handlers);
    await settle();
    stop();

    expect(statuses).toContain("offline");
  });

  it("reports reconnecting rather than failing when the request errors", async () => {
    const { statuses, handlers } = collect();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    const stop = connectLiveStream(handlers);
    await settle();
    stop();

    expect(statuses).toContain("reconnecting");
  });

  it("waits instead of opening an unauthenticated stream", async () => {
    authStorage.clearToken();
    const { handlers } = collect();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const stop = connectLiveStream(handlers);
    await settle();
    stop();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends the bearer token and asks for an event stream", async () => {
    const { handlers } = collect();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: sseBody([frame("alert.created", {}, 1)]),
    });
    vi.stubGlobal("fetch", fetchMock);

    const stop = connectLiveStream(handlers);
    await settle();
    stop();

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer test-token");
    expect(init.headers.Accept).toBe("text/event-stream");
  });

  it("stops cleanly and makes no further requests", async () => {
    const { handlers } = collect();
    const fetchMock = vi.fn().mockRejectedValue(new Error("down"));
    vi.stubGlobal("fetch", fetchMock);

    const stop = connectLiveStream(handlers);
    await settle();
    stop();
    const callsAtStop = fetchMock.mock.calls.length;

    await new Promise((resolve) => setTimeout(resolve, 60));
    expect(fetchMock.mock.calls.length).toBe(callsAtStop);
  });
});
