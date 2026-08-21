# ADR 0006 — Frontend testing: Vitest + React Testing Library; Playwright deferred

- **Status:** Accepted
- **Date:** 2026-08-21

## Context

The dashboard had no automated tests at all. CI ran `eslint` and `tsc -b`,
which catch syntax and type errors and nothing about behaviour: not a broken
login, not a mishandled 401, not a role gate that shows a control it should
hide.

## Decision

**Vitest 4 + React Testing Library + jsdom + axe-core.** Verified against the
actual project before committing the dependencies: Vitest 4 declares
`vite: ^6 || ^7 || ^8` (this project is on Vite 8) and RTL 16.3 declares
`react: ^18 || ^19` (this project is on React 19).

`fetch` is stubbed per test rather than mocked at the module boundary, so the
real `src/lib/api.ts` — refresh-and-retry, single-flight, CSRF header,
credential mode, error normalisation — is the code under test rather than a
stand-in for it.

Test files live under `src/**/*.test.{ts,tsx}` and are inside
`tsconfig.app.json`'s `include`, so `npm run build` type-checks them. That is
deliberate: it caught a real typing error in this sprint's own test code.

### Why Playwright is deferred

Playwright is the right tool for a genuinely cross-process journey, and it is
not being ruled out. It is deferred because, for the journeys this sprint
needs to cover, it would cost more than it returns:

1. **The journeys are already covered at a level that fails faster.** Login,
   silent refresh, logout, expired/revoked session, role gates, 401/403/429,
   backend-unreachable and loading/empty/error states are all assertable in
   jsdom against the real API client. A browser adds startup cost and
   flakiness without adding assertions.
2. **Cross-tenant isolation is a server property.** Testing it through a
   browser tests the UI's ability to render what the server returned. The
   real guarantee is asserted directly, 25 ways, in
   `tests/backend/test_tenant_isolation.py`.
3. **CI cost and the artifact policy.** A browser run wants a live backend and
   a live database, and its natural failure output is a trace/video/screenshot
   bundle — exactly the persisted artifacts ADR 0004 forbids while the
   account's storage is exhausted. Adding it *and* disabling its diagnostics
   would leave a slow suite that is hard to debug.
4. **Unused test infrastructure is scaffolding debt.** This sprint removed an
   unused Auth0 scaffold and an unused Expo app for that reason. Adding a
   Playwright harness with one smoke test, to be maintained by nobody, would
   reintroduce the same problem in a new place.

### What would change the decision

- A journey that genuinely cannot be expressed in jsdom — real navigation, a
  service worker, file download/upload, multi-tab session behaviour, or
  verifying that the HttpOnly cookie is actually withheld from JavaScript
  (jsdom's cookie jar does not enforce HttpOnly, so that property is currently
  asserted server-side instead).
- Hosting resuming, which would give a stable URL to run against.
- Visual regressions becoming a recurring source of defects.

## Consequences

- 63 frontend tests run in ~6s with no browser download and no artifacts.
- axe-core gives a machine-detectable accessibility floor. It found a real
  defect immediately: the login page's icon-only password toggle had no
  accessible name and was excluded from the tab order. **A pass means "no
  known machine-detectable violation" and nothing more** — axe cannot tell
  whether a flow makes sense to someone using a screen reader, and this
  project has done no manual assistive-technology testing.
- `color-contrast` and `region` rules are disabled in the harness: jsdom
  renders no stylesheet, so computed colour is meaningless, and tests mount
  fragments rather than whole documents. Contrast is a design-token concern,
  verified against the palette in `docs/adr/`-adjacent design notes.
- Tests must not leave a `fetch` promise permanently pending: the api layer's
  single-flight refresh holds one module-level promise, and a dangling one
  parks every later test in the file. Learned the hard way here.
