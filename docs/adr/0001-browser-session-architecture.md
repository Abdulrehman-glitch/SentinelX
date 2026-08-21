# ADR 0001 — Browser session architecture: in-memory access token + HttpOnly rotating refresh cookie

- **Status:** Accepted
- **Date:** 2026-08-21

## Context

The dashboard stored its bearer JWT in `localStorage` under `sx_auth_token`.
That produced four compounding problems:

1. **XSS reads the credential directly.** Any script running on the origin
   could read `localStorage` and exfiltrate a working token.
2. **The token lived for 24 hours** (`ACCESS_TOKEN_EXPIRE_MINUTES=1440`), so a
   stolen one stayed useful for a day.
3. **Nothing was revocable.** Tokens were stateless with no server-side record.
   `POST /auth/logout` wrote an audit row and returned 200; the token it
   "revoked" kept working. Deactivating a user did not end their session either.
4. **JWT validation was minimal** — signature and expiry only. No `iss`, no
   `aud`, no token purpose. A token minted by any other service sharing the
   secret would have been accepted, and a token that simply omitted `exp` would
   have validated forever, because PyJWT only checks claims that are present.

The API also serves non-browser clients (desktop, Android, embedded bridge)
that authenticate with **device tokens**, not user JWTs. Any redesign had to
leave that path completely untouched.

## Decision

A **split-credential** design, sometimes called the refresh-cookie or
"BFF-lite" pattern.

| Credential | Lifetime | Storage | Reachable from JS |
|---|---|---|---|
| Access token (JWT) | 15 min | JavaScript closure, in memory | yes, by design |
| Refresh token (opaque, 48 random bytes) | 14 days sliding, 30 days absolute | `sx_refresh` cookie: HttpOnly, SameSite, path-scoped to `/api/v1/auth` | **no** |
| CSRF token | same as refresh | `sx_csrf` cookie, readable | yes, required |

Mechanics:

- **Server-side sessions.** `user_sessions` rows back every sign-in. Access
  tokens carry `sid`; `get_current_user` resolves that session on every request
  and rejects the token if it is missing, revoked or expired. This is what makes
  logout real.
- **Rotation with replay detection.** Each `POST /auth/refresh` spends the
  presented token and issues a successor, keeping the previous hash. Presenting
  a spent token means two parties hold tokens from one family; the server cannot
  tell which is the thief, so it revokes the whole family and logs a
  `session_reuse_detected` security event. Failing closed is the point.
- **Signed double-submit CSRF.** `/auth/refresh` is cookie-authenticated and
  therefore has a CSRF surface. The `sx_csrf` value is
  `HMAC-SHA256(jwt_secret, "csrf:" + refresh_token_hash)`. The server recomputes
  it from the session it resolved via the HttpOnly cookie, so an attacker who
  can *write* cookies but not *read* the refresh cookie cannot produce a
  matching pair. Naive double-submit fails exactly that attacker.
- **Hardened decode.** `iss`, `aud`, `typ: "access"`, `jti`, `nbf` are all set
  and all *required* on decode via PyJWT's `options={"require": [...]}`.
  Reserved claims cannot be overridden through `extra_claims`.
- **Claims rebuilt on refresh** from the live user row, so a role change takes
  effect within 15 minutes instead of persisting for a day.
- **Dev vs production.** `SESSION_COOKIE_SECURE` is unset by default and
  resolves to `true` under `APP_ENV=production`, `false` otherwise. Production
  refuses to start with it false, and `SameSite=None` without `Secure` is a
  startup error rather than a mysterious "login works, refresh 401".

### Why the access token is still a bearer header, not a cookie

Cookie-authenticating the whole API would put a CSRF surface on all ~90
endpoints instead of one, and would break Swagger's Authorize flow and the load
tests. Keeping `Authorization: Bearer` means the blast radius of this change is
the auth module and the frontend's request helper — everything else, including
every device-token route, is untouched.

### Why not Auth0/Clerk

An external IdP would not have fixed the actual defects (no revocation, weak
claim validation) without the same session work, and would add a vendor
dependency and a billing surface to a project whose hard constraint is neither.
The unused Auth0 scaffold is removed instead (ADR 0005).

## Consequences

- XSS can still steal the *current* access token — no browser design prevents
  that — but it expires in 15 minutes and cannot be renewed once the tab closes,
  because the refresh token is unreadable from script.
- Every authenticated request now costs one indexed primary-key lookup on
  `user_sessions`. Measured against a `db.get(User, ...)` that already happened
  on the same path, this is a second point lookup, not a scan.
- Tests can no longer fabricate a bare JWT; `tests/backend/helpers.py`
  `issue_access_token()` mints a session-backed one. That is a feature — it
  means no test can accidentally prove the un-revocable path still works.
- Non-browser agents are unaffected: they never used this flow.
- `tests/backend/test_auth_sessions.py` pins all of the above (31 tests).

## Alternatives considered

- **Keep localStorage, shorten expiry.** Rejected: does not address revocation,
  and a short expiry without a refresh mechanism means users get logged out
  every 15 minutes.
- **Full BFF (server-side session cookie for everything).** Rejected: correct
  for a same-origin monolith, disproportionate here, and would have required
  reworking every route and both non-browser client families.
- **Refresh token as a second JWT.** Rejected: a self-contained refresh token
  cannot be revoked without a server-side list anyway, so the list is the real
  mechanism — at which point an opaque random token is simpler and leaks nothing.
