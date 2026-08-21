# ADR 0005 — Retiring the Expo agent, the Auth0 scaffold and the Pages workflow

- **Status:** Accepted
- **Date:** 2026-08-21

## Context

Three pieces of the repository were carried but not used. Each looked harmless
in isolation and cost something real in aggregate: dependency surface, reviewer
attention, and — worst — the impression that two different answers to the same
question were both live.

## Decision

### 1. `agents/mobile-expo/` — retired

Evidence gathered before deciding:

| Signal | Finding |
|---|---|
| Purpose | Duplicates the native Android agent (Kotlin/Compose, v3.0.0, signed APK, CI) and the native iOS agent (Swift 6, CI) — a **third** mobile stack for the same telemetry job |
| Progress | No functional commit since it was created; the only commit touching it is the 2026-07-14 repo reorganisation, which merely moved it |
| Documentation | `README.md` was still the untouched `create-expo-app` boilerplate ("Welcome to your Expo app") |
| Screens | Two routes, one of which (`explore.tsx`) is template boilerplate |
| Tests / CI | None, and no workflow |
| Dependency burden | 44 direct dependencies, 882 lockfile entries, **20 npm advisories (11 high, 9 moderate)** |
| Prior status | Already logged as open issue #7 in `docs/PRODUCTION_READINESS_AUDIT.md` — "work-in-progress and ships to nobody" |

A third mobile client with no owner, no tests, no CI and 11 high-severity
advisories is not an architectural option being kept open; it is an
unmaintained attack surface that makes the repository's own security reporting
noisier and less trustworthy.

Recovering it takes one `git checkout` of the path against the commit before
this one. Nothing about the platform prevents an Expo client later — but it
should start from a decision, not from a stale scaffold.

### 2. Auth0 scaffold — retired

`@auth0/auth0-react`, `Auth0Provider`, `Auth0CallbackPage`, `auth0Config.ts`,
the `/auth0/callback` route, the login-page button and the two `VITE_AUTH0_*`
env vars. It was gated behind config that was never set, and it authenticated
nothing: the platform has always used its own JWT flow, and every API route
validates that and only that.

The decisive argument is not the dead code, it is the timing: this sprint
rebuilt the browser session architecture (ADR 0001). Carrying a second,
half-wired authentication direction through that work is how the wrong one
ends up being used by mistake. See ADR 0001 for why an external IdP would not
have solved the actual defects anyway.

### 3. `.github/workflows/pages.yml` — retired

Built and uploaded a ~7.5 MB Pages artifact on every frontend push while
publishing was manual anyway, and duplicated the lint and build that
`frontend.yml` already runs. With hosting paused (ADR 0003) and artifact
storage exhausted (ADR 0004), it was pure cost. Restoring it is one file from
git history.

### 4. `scripts/azure_teardown.ps1` — retired

Nothing referenced it and there is nothing left to tear down (ADR 0003).

## Consequences

- One mobile agent per platform, both native, both with CI.
- One authentication direction, tested (`tests/backend/test_auth_sessions.py`,
  `frontend/src/contexts/__tests__/AuthContext.test.tsx`).
- `npm audit` across the whole repository is now clean, so a future advisory is
  a signal rather than noise in a pile of 20 pre-existing ones.
- `docs/PRODUCTION_READINESS_AUDIT.md` issue #7 is resolved by removal. That
  document keeps its original wording — it is a historical audit, and editing
  it to say something it did not say at the time would be falsifying the record.
