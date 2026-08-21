# ADR 0004 — CI validates, CI does not publish

- **Status:** Accepted
- **Date:** 2026-08-21

## Context

The account's GitHub Actions artifact storage was reported at 100% of its
allowance. A read-only audit of this repository found:

| Source | Live size | Verdict |
|---|---|---|
| Actions artifacts (4 `.dockerbuild` build records) | ~202 KB | tiny, but growing on every `main` push |
| Actions artifacts (8 unsigned `.ipa`, 14-day retention) | ~3.4 MB | all expired at audit time; recurring |
| Actions caches (4 CodeQL overlay databases) | 72 MB | free — 10 GB/repo allowance, not billed |
| GHCR `sentinelx-api` package | not enumerable with the current token scopes | free — package is **public** |

Three facts, verified against current GitHub documentation rather than repository
comments:

1. Standard GitHub-hosted runners are free for public repositories. `macos-15`
   is a **standard** runner (3-core M1) per the current runner reference — only
   *larger* runners are billed for public repos. iOS CI is therefore free.
2. Cache storage is a separate 10 GB per-repository allowance and is not the
   billed artifact storage.
3. GitHub Packages is free for **public** packages; only private package storage
   meters against the plan quota. An anonymous pull of
   `ghcr.io/abdulrehman-glitch/sentinelx-api` returns HTTP 200, confirming it is
   public.

So this repository was not the main consumer of the exhausted quota — but it was
adding to it on every push, for no operational benefit while hosting is paused.

## Decision

**Routine CI persists nothing. Publishing is manual, explicit and separate.**

1. `docker.yml` builds with `load: true` instead of `push`, drops `packages:
   write` and the registry login entirely, and sets
   `DOCKER_BUILD_RECORD_UPLOAD: false` — that default is what produced every
   `.dockerbuild` artifact the repository had. The smoke test and the Trivy
   HIGH/CRITICAL scan are unchanged, because that is the part with value.
2. `container-publish.yml` is the only workflow that publishes anything. It has
   no `push` or `pull_request` trigger and additionally requires the operator to
   type `publish` into a confirmation input, checked again as a job-level `if:`.
   A mis-click does nothing.
3. `ios.yml` keeps the simulator test run **and** the Release/iphoneos device
   build — dropping compile coverage to save storage would be trading the wrong
   thing. Only the `.ipa` packaging and upload move behind a manual dispatch
   input, at `retention-days: 1` (GitHub's minimum for public repositories).
4. `pages.yml` is removed. It built and uploaded a ~7.5 MB Pages artifact on
   every frontend push while publishing was manual anyway, and duplicated the
   lint/build that `frontend.yml` already runs.
5. Test results, coverage and build output stay in job logs. Logs do not count
   against the artifact allowance.
6. Standard runners only, always. No larger runners, no self-hosted runners.

## Consequences

- Routine SentinelX CI can no longer increase artifact-storage pressure at all:
  after this change there is exactly one `upload-artifact` step in the tree and
  it is unreachable from `push`/`pull_request`.
- Retention for *new* artifacts is capped per-workflow at 1 day. Repository-wide
  artifact retention (Settings → Actions → General) has no REST endpoint and
  remains an owner-only UI action; see the sprint report.
- Historical artifacts are untouched. Deleting them is the owner's call.
- Reintroducing Pages later means restoring one deleted file from git history.
