// §32 — every surfaced error carries a human explanation, an action hint,
// whether retrying is safe, and a short diagnostic reference id.

export type ErrorKind =
  | "invalid_credentials"
  | "session_expired"
  | "permission_denied"
  | "rate_limited"
  | "offline"
  | "timeout"
  | "server_unavailable"
  | "validation"
  | "not_found"
  | "device_token_invalid"
  | "unknown";

export interface AppError {
  kind: ErrorKind;
  title: string;
  message: string;
  retryable: boolean;
  status?: number;
  reference: string;
  detail?: string;
}

export function newReference(): string {
  // Short, log-correlatable id shown to the user; not a secret.
  return `SX-${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`;
}

const COPY: Record<ErrorKind, { title: string; message: string; retryable: boolean }> = {
  invalid_credentials: {
    title: "Sign-in failed",
    message: "The email or password is incorrect. Check the details and try again.",
    retryable: false,
  },
  session_expired: {
    title: "Session expired",
    message: "Your session has ended. Sign in again to continue.",
    retryable: false,
  },
  permission_denied: {
    title: "Not permitted",
    message: "Your role does not allow this action. Contact an administrator if you need access.",
    retryable: false,
  },
  rate_limited: {
    title: "Too many attempts",
    message: "The server is limiting requests. Wait a moment before trying again.",
    retryable: true,
  },
  offline: {
    title: "You're offline",
    message: "No internet connection. Showing the last cached data where available.",
    retryable: true,
  },
  timeout: {
    title: "Request timed out",
    message: "The server took too long to respond. Check your connection and retry.",
    retryable: true,
  },
  server_unavailable: {
    title: "Server unavailable",
    message: "SentinelX could not be reached. It may be down or the URL may be wrong.",
    retryable: true,
  },
  validation: {
    title: "Request rejected",
    message: "The server rejected the request data.",
    retryable: false,
  },
  not_found: {
    title: "Not found",
    message: "The requested record no longer exists or is outside your organisation.",
    retryable: false,
  },
  device_token_invalid: {
    title: "Agent credential invalid",
    message: "This device's agent token was revoked or is stale. Re-enrol the agent from Settings.",
    retryable: false,
  },
  unknown: {
    title: "Something went wrong",
    message: "An unexpected error occurred.",
    retryable: true,
  },
};

export function buildError(kind: ErrorKind, opts?: { status?: number; detail?: string }): AppError {
  const copy = COPY[kind];
  return {
    kind,
    title: copy.title,
    message: copy.message,
    retryable: copy.retryable,
    status: opts?.status,
    detail: opts?.detail,
    reference: newReference(),
  };
}

export function kindFromStatus(status: number, opts?: { authRequest?: boolean; deviceAuth?: boolean }): ErrorKind {
  if (status === 401) {
    if (opts?.deviceAuth) return "device_token_invalid";
    return opts?.authRequest ? "invalid_credentials" : "session_expired";
  }
  if (status === 403) return "permission_denied";
  if (status === 404) return "not_found";
  if (status === 422 || status === 400) return "validation";
  if (status === 429) return "rate_limited";
  if (status >= 500) return "server_unavailable";
  return "unknown";
}

export function isAppError(err: unknown): err is AppError {
  return typeof err === "object" && err !== null && "kind" in err && "reference" in err;
}

export function toAppError(err: unknown): AppError {
  if (isAppError(err)) return err;
  if (err instanceof Error) {
    if (err.name === "AbortError") return buildError("timeout");
    if (/network request failed/i.test(err.message)) return buildError("server_unavailable", { detail: err.message });
    return buildError("unknown", { detail: err.message });
  }
  return buildError("unknown");
}
