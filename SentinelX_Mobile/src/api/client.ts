import { buildError, kindFromStatus, toAppError } from "@/lib/errors";
import { getBaseUrlSync } from "@/lib/config";

type TokenProvider = () => string | null;

let getAccessToken: TokenProvider = () => null;
let onSessionExpired: () => void = () => {};

// AuthContext wires these at startup; avoids a circular import.
export function configureClient(opts: { tokenProvider: TokenProvider; sessionExpiredHandler: () => void }) {
  getAccessToken = opts.tokenProvider;
  onSessionExpired = opts.sessionExpiredHandler;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  // "user" attaches the JWT; "device" attaches the agent token; "none" is anonymous.
  auth?: "user" | "device" | "none";
  deviceToken?: string;
  timeoutMs?: number;
  // Marks login-style calls so a 401 reads as bad credentials, not expiry.
  authRequest?: boolean;
  signal?: AbortSignal;
}

export interface ApiMeta {
  latencyMs: number;
  serverDate: string | null;
  status: number;
}

let lastMeta: ApiMeta | null = null;
export function getLastRequestMeta(): ApiMeta | null {
  return lastMeta;
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = "user", timeoutMs = 15_000 } = opts;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  if (auth === "user") {
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  } else if (auth === "device") {
    if (!opts.deviceToken) throw buildError("device_token_invalid");
    headers.Authorization = `Bearer ${opts.deviceToken}`;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  if (opts.signal) {
    opts.signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  const started = Date.now();
  let response: Response;
  try {
    response = await fetch(`${getBaseUrlSync()}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    throw toAppError(err);
  } finally {
    clearTimeout(timer);
  }

  lastMeta = {
    latencyMs: Date.now() - started,
    serverDate: response.headers.get("date"),
    status: response.status,
  };

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const payload = await response.json();
      detail = typeof payload?.detail === "string" ? payload.detail : JSON.stringify(payload?.detail ?? payload);
    } catch {
      // non-JSON error body; keep generic copy
    }
    const kind = kindFromStatus(response.status, {
      authRequest: opts.authRequest,
      deviceAuth: auth === "device",
    });
    if (kind === "session_expired") onSessionExpired();
    throw buildError(kind, { status: response.status, detail });
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
