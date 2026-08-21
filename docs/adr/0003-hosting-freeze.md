# ADR 0003 — Hosting is paused; SentinelX runs locally only

- **Status:** Accepted
- **Date:** 2026-08-21
- **Supersedes:** the Azure App Service deployment described in `CHANGELOG.md` and `docs/PRODUCTION_READINESS_AUDIT.md`

## Context

SentinelX was deployed to Azure (App Service F1 + PostgreSQL Flexible Server +
Storage static website) on an Azure for Students subscription. Those credits are
gone. The subscription is no longer usable and the deployment is dead: nothing
answers on `sentinelx-api.azurewebsites.net`.

The repository nevertheless still carried live Azure operational residue —
`scripts/azure_teardown.ps1`, install instructions telling an operator to point
the Android release APK at the dead hostname, and a local `.env` for the
embedded bridge whose API base URL was the dead host. A newcomer reading the
repository could reasonably have concluded Azure was still part of the running
system.

## Decision

**Hosting is paused indefinitely. SentinelX has no active cloud dependency.**

1. Active Azure configuration is removed: `scripts/azure_teardown.ps1` is
   deleted (nothing referenced it and there is nothing left to tear down), and
   instructions that presented the Azure URL as a working target now describe
   the local/LAN path instead.
2. Historical statements are preserved verbatim. `CHANGELOG.md`,
   `docs/PRODUCTION_READINESS_AUDIT.md` and `docs/releases/` accurately record
   that an Azure deployment existed and what happened to it. Rewriting them
   would be falsifying the project record, which is worse than the drift it
   would fix. Current-instruction documents are corrected; historical documents
   are left alone.
3. The GitHub Pages deployment workflow is removed (see ADR 0004).
4. No replacement host is provisioned. Not Azure, not GCP, not AWS, not Vercel,
   not Neon, not a free-tier stand-in. Every one of those carries either a
   billing surface or an expiry that turns into one.

## Consequences

- The Android *release* APK has no HTTPS target, because it refuses cleartext.
  Local and LAN work uses a debug build; `agents/android-native/INSTALL_GUIDE.md`
  now says so directly rather than offering a dead URL as the happy path.
- The `agents/ios-native/` mobile dev server and the main API both run locally.
- `docker.yml` still builds, smoke-tests and CVE-scans the API image, because
  that validation is worth keeping whether or not anything is deployed. It just
  no longer publishes (ADR 0004).
- Resuming hosting is a deliberate, costed decision. The manual publish path in
  `.github/workflows/container-publish.yml` is preserved so that decision does
  not also require rebuilding the pipeline from scratch.

## Alternatives considered

- **Keep a free-tier host running.** Rejected: every free tier either expires,
  requires a card on file, or silently converts to paid. The owner's explicit
  constraint is that no operation may create a surprise charge.
- **Delete all Azure mentions repository-wide.** Rejected: that destroys
  accurate project history, which the coursework record depends on.
