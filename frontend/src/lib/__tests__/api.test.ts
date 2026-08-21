import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  API_BASE_URL,
  refreshAccessToken,
  sentinelxApi,
  setSessionEndedHandler,
} from "../api";
import { authStorage, CSRF_COOKIE_NAME } from "../authStorage";

function fetchMock() {
  return globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
}

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

function noBodyResponse(status: number) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: async () => {
      throw new Error("no body");
    },
    text: async () => "",
  } as unknown as Response;
}

const REFRESHED = {
  access_token: "refreshed-token",
  token_type: "bearer",
  expires_in: 900,
  user: { id: "u1", email: "a@b.c", full_name: "A", role: "admin" },
};

beforeEach(() => {
  authStorage.clearToken();
  setSessionEndedHandler(null);
  document.cookie = `${CSRF_COOKIE_NAME}=csrf-token`;
});

afterEach(() => {
  authStorage.clearToken();
  setSessionEndedHandler(null);
});

describe("request headers and credentials", () => {
  it("sends the access token as a bearer header when one is held", async () => {
    authStorage.setToken("access-token", 900);
    fetchMock().mockResolvedValueOnce(jsonResponse([]));

    await sentinelxApi.getUsers();

    const [, init] = fetchMock().mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer access-token");
  });

  it("always includes credentials so the HttpOnly refresh cookie travels", async () => {
    fetchMock().mockResolvedValueOnce(jsonResponse({ status: "ok" }));

    await sentinelxApi.getHealth();

    const [, init] = fetchMock().mock.calls[0];
    expect(init.credentials).toBe("include");
  });

  it("echoes the CSRF cookie back in the header", async () => {
    fetchMock().mockResolvedValueOnce(jsonResponse([]));

    await sentinelxApi.getUsers();

    const [, init] = fetchMock().mock.calls[0];
    expect(init.headers["X-CSRF-Token"]).toBe("csrf-token");
  });

  it("omits the bearer header on endpoints marked unauthenticated", async () => {
    authStorage.setToken("access-token", 900);
    fetchMock().mockResolvedValueOnce(jsonResponse(REFRESHED));

    await sentinelxApi.login({ email: "a@b.c", password: "x" });

    const [, init] = fetchMock().mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
  });
});

describe("401 handling: silent refresh and retry", () => {
  it("refreshes once and replays the original request", async () => {
    authStorage.setToken("stale-token", 900);

    fetchMock()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401)) // original
      .mockResolvedValueOnce(jsonResponse(REFRESHED)) // /auth/refresh
      .mockResolvedValueOnce(jsonResponse([{ id: "d1" }])); // replay

    const result = await sentinelxApi.getUsers();

    expect(result).toEqual([{ id: "d1" }]);
    expect(fetchMock()).toHaveBeenCalledTimes(3);
    expect(fetchMock().mock.calls[1][0]).toBe(`${API_BASE_URL}/auth/refresh`);
    // The replay must carry the NEW token, not the one that just failed.
    expect(fetchMock().mock.calls[2][1].headers.Authorization).toBe("Bearer refreshed-token");
  });

  it("gives up after one refresh rather than looping", async () => {
    authStorage.setToken("stale-token", 900);

    fetchMock()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(jsonResponse(REFRESHED))
      .mockResolvedValueOnce(jsonResponse({ detail: "still expired" }, 401));

    await expect(sentinelxApi.getUsers()).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock()).toHaveBeenCalledTimes(3);
  });

  it("notifies the session-ended handler when the refresh itself fails", async () => {
    authStorage.setToken("stale-token", 900);
    const onEnded = vi.fn();
    setSessionEndedHandler(onEnded);

    fetchMock()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: "session gone" }, 401));

    await expect(sentinelxApi.getUsers()).rejects.toBeInstanceOf(ApiError);

    expect(onEnded).toHaveBeenCalledTimes(1);
    expect(authStorage.getToken()).toBeNull();
  });

  it("does not attempt a refresh when there is no CSRF cookie", async () => {
    // No cookie means no session at all — asking the server would just be a
    // guaranteed 401.
    document.cookie = `${CSRF_COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
    authStorage.setToken("stale-token", 900);

    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401));

    await expect(sentinelxApi.getUsers()).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock()).toHaveBeenCalledTimes(1);
  });

  it("coalesces concurrent refreshes into a single call", async () => {
    // This is not an optimisation. Refresh ROTATES the token, so a second
    // parallel refresh would present an already-spent one and trip the
    // server's replay detection — logging the user out over an attack they
    // did not suffer.
    fetchMock().mockResolvedValue(jsonResponse(REFRESHED));

    await Promise.all([refreshAccessToken(), refreshAccessToken(), refreshAccessToken()]);

    const refreshCalls = fetchMock().mock.calls.filter((call) =>
      String(call[0]).endsWith("/auth/refresh"),
    );
    expect(refreshCalls).toHaveLength(1);
  });

  it("allows a fresh refresh after the previous one settles", async () => {
    fetchMock().mockResolvedValue(jsonResponse(REFRESHED));

    await refreshAccessToken();
    await refreshAccessToken();

    const refreshCalls = fetchMock().mock.calls.filter((call) =>
      String(call[0]).endsWith("/auth/refresh"),
    );
    expect(refreshCalls).toHaveLength(2);
  });
});

describe("other failure states", () => {
  it("surfaces a 403 without trying to refresh", async () => {
    // 403 is "you are who you say you are and still may not do this" —
    // refreshing would change nothing and would hide the real reason.
    authStorage.setToken("access-token", 900);
    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "Insufficient permissions." }, 403));

    await expect(sentinelxApi.getUsers()).rejects.toMatchObject({
      status: 403,
      message: "Insufficient permissions.",
    });
    expect(fetchMock()).toHaveBeenCalledTimes(1);
  });

  it("gives a 429 a human-readable message even with an empty body", async () => {
    authStorage.setToken("access-token", 900);
    fetchMock().mockResolvedValueOnce(noBodyResponse(429));

    await expect(sentinelxApi.getUsers()).rejects.toMatchObject({
      status: 429,
      message: "Too many requests. Please wait a moment before trying again.",
    });
  });

  it("propagates a network failure when the backend is unreachable", async () => {
    authStorage.setToken("access-token", 900);
    fetchMock().mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(sentinelxApi.getUsers()).rejects.toThrow("Failed to fetch");
  });

  it("flattens FastAPI's structured 422 detail into one readable string", async () => {
    authStorage.setToken("access-token", 900);
    fetchMock().mockResolvedValueOnce(
      jsonResponse(
        {
          detail: [
            { loc: ["body", "name"], msg: "Field required" },
            { loc: ["body", "threshold"], msg: "Input should be a number" },
          ],
        },
        422,
      ),
    );

    await expect(sentinelxApi.getUsers()).rejects.toMatchObject({
      status: 422,
      message: "body.name: Field required; body.threshold: Input should be a number",
    });
  });

  it("returns undefined for a 204 rather than trying to parse a body", async () => {
    authStorage.setToken("access-token", 900);
    fetchMock().mockResolvedValueOnce(noBodyResponse(204));

    await expect(sentinelxApi.getUsers()).resolves.toBeUndefined();
  });

  it("falls back to the raw body when the error is not JSON", async () => {
    authStorage.setToken("access-token", 900);
    fetchMock().mockResolvedValueOnce({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: async () => {
        throw new Error("not json");
      },
      text: async () => "<html>502 Bad Gateway</html>",
    } as unknown as Response);

    await expect(sentinelxApi.getUsers()).rejects.toMatchObject({ status: 502 });
  });
});

describe("session endpoints", () => {
  it("stores the token and its lifetime after a successful refresh", async () => {
    fetchMock().mockResolvedValueOnce(jsonResponse(REFRESHED));

    await expect(refreshAccessToken()).resolves.toBe(true);
    expect(authStorage.getToken()).toBe("refreshed-token");
    expect(authStorage.msUntilExpiry()).toBeGreaterThan(0);
  });

  it("reports failure without throwing when the session is gone", async () => {
    fetchMock().mockResolvedValueOnce(jsonResponse({ detail: "gone" }, 401));

    await expect(refreshAccessToken()).resolves.toBe(false);
    expect(authStorage.getToken()).toBeNull();
  });

  it("survives a rejected refresh request instead of leaking the rejection", async () => {
    fetchMock().mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(refreshAccessToken()).resolves.toBe(false);
  });
});
