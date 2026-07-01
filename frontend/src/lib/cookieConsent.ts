// Cookie / storage consent handling.
//
// Essential storage (auth token, saved UI preferences) is always allowed —
// it is required for the app to function. Non-essential cookies are only
// written after the user explicitly accepts.

export type ConsentChoice = "accepted" | "declined";

const CONSENT_KEY = "sx_cookie_consent";
const CONSENT_COOKIE = "sx_consent";

export function getConsentChoice(): ConsentChoice | null {
  try {
    const stored = localStorage.getItem(CONSENT_KEY);
    if (stored === "accepted" || stored === "declined") return stored;
  } catch {
    // ignore
  }
  // Fall back to the cookie (survives localStorage clears).
  const match = document.cookie.match(/(?:^|;\s*)sx_consent=(accepted|declined)/);
  return (match?.[1] as ConsentChoice) ?? null;
}

export function hasConsentChoice(): boolean {
  return getConsentChoice() !== null;
}

export function setConsentChoice(choice: ConsentChoice): void {
  try {
    localStorage.setItem(CONSENT_KEY, choice);
  } catch {
    // ignore
  }
  // Record the decision itself in a cookie so it is respected across sessions.
  // Only "accepted" additionally unlocks non-essential cookies elsewhere.
  const oneYear = 60 * 60 * 24 * 365;
  document.cookie = `${CONSENT_COOKIE}=${choice}; path=/; max-age=${oneYear}; SameSite=Lax`;
}

/** True when the user has accepted non-essential cookies. */
export function nonEssentialCookiesAllowed(): boolean {
  return getConsentChoice() === "accepted";
}

/**
 * Write a functional cookie only when the user has accepted. Used to mirror
 * lightweight preferences (e.g. theme) for a faster first paint next visit.
 */
export function setFunctionalCookie(name: string, value: string, maxAgeSeconds = 60 * 60 * 24 * 180): void {
  if (!nonEssentialCookiesAllowed()) return;
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAgeSeconds}; SameSite=Lax`;
}
