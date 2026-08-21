/**
 * In-memory access-token store.
 *
 * The access token deliberately never touches localStorage or sessionStorage.
 * Both are readable by any script on the origin, which is what made the
 * previous design's 24-hour bearer token a one-line XSS payload away from
 * full account takeover.
 *
 * What replaces persistence: the refresh token lives in an HttpOnly cookie
 * the browser attaches to /api/v1/auth automatically. On a page reload the
 * app has no access token, calls /auth/refresh once, and gets a new one — so
 * the session survives a reload without the credential ever being readable
 * from script. See docs/adr/0001-browser-session-architecture.md.
 */

type Listener = (token: string | null) => void;

let accessToken: string | null = null;
let expiresAtMs: number | null = null;
const listeners = new Set<Listener>();

function notify() {
  for (const listener of listeners) listener(accessToken);
}

export const authStorage = {
  getToken() {
    return accessToken;
  },

  setToken(token: string, expiresInSeconds?: number) {
    accessToken = token;
    expiresAtMs =
      typeof expiresInSeconds === "number" ? Date.now() + expiresInSeconds * 1000 : null;
    notify();
  },

  clearToken() {
    accessToken = null;
    expiresAtMs = null;
    notify();
  },

  /** Milliseconds until expiry, or null when the lifetime is unknown. */
  msUntilExpiry(): number | null {
    return expiresAtMs === null ? null : expiresAtMs - Date.now();
  },

  subscribe(listener: Listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

/**
 * Reads a non-HttpOnly cookie. Used only for the CSRF token, which is
 * readable on purpose — the double-submit check needs the SPA to echo it
 * back in a header. The refresh cookie itself is HttpOnly and returns
 * undefined here, which is the intended behaviour.
 */
export function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;

  const prefix = `${name}=`;
  for (const part of document.cookie.split("; ")) {
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.slice(prefix.length));
    }
  }
  return undefined;
}

export const CSRF_COOKIE_NAME = "sx_csrf";
export const CSRF_HEADER_NAME = "X-CSRF-Token";
