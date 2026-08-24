# ADR 0012 — Shared rate-limit state, and a live channel built on PostgreSQL

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** [0008 — transactional outbox and worker](0008-transactional-outbox-and-worker.md),
  [0009 — canonical telemetry model](0009-canonical-telemetry-model.md),
  [0010 — PostgreSQL telemetry storage](0010-postgresql-telemetry-storage.md)

## Context

Two v3.3 items were deferred together because they look like the same problem:
both are usually solved by adding Redis or Valkey.

**Rate limiting.** The counters lived in each API process's memory. With one
uvicorn worker that is correct. With four, `RATE_LIMIT_LOGIN=15/minute` is
really sixty per minute, and the effective number drifts with however many
workers happen to be running — a security control whose value nobody can state.

**Live updates.** The console polled. `domain_events` existed as a model with
no producer and no reader: the durable half of a live stream that had not been
built yet.

The obvious answer to both is Valkey — shared counters, pub/sub fan-out. Two
facts complicated that. Valkey publishes no official Windows build, and this
project is developed on Windows without Docker or WSL; and SentinelX already
mandates PostgreSQL, so a second stateful dependency raises the cost of running
the thing at all — which, for a project whose local demo is a deliverable, is a
real cost rather than an abstract one.

## Decision

### Rate limiting: PostgreSQL by default, Valkey when it is worth it

Counters move behind the `limits` `Storage` interface, so all ten existing
`@limiter.limit(...)` decorators are untouched.

`RATE_LIMIT_BACKEND=auto` (the default) resolves to a PostgreSQL storage
implemented in `app/core/rate_limit_storage.py`. One `INSERT ... ON CONFLICT`
per increment; the window rolls forward inside the same statement, so an
expired window is replaced rather than added to and correctness never depends
on a sweeper. Pruning expired rows is housekeeping, and the worker does it
(`maintenance.prune_rate_limits`, every 6 hours).

`RATE_LIMIT_BACKEND=valkey` hands `limits` a `valkey://` URL, which it already
supports natively. Pinned at `valkey/valkey:8.1.9-alpine` behind a compose
profile. Persistence is deliberately off: a lost counter means a caller gets a
fresh budget, so nothing irreplaceable is stored there.

The counters run on their own autocommit connection rather than the request's
session. A limit consumed by a request that then rolls back must stay consumed,
or a caller could refund their own budget by making the work fail.

**Failure is explicit.** An unreachable shared store falls back to per-process
counting — still enforcing, no longer shared — `/health` reports `degraded` and
says why, and the reason is logged. It never starts allowing everything because
a dependency is down.

### Live events: SSE over PostgreSQL, not pub/sub

`GET /api/v1/events/stream` is Server-Sent Events. The traffic is one-way, so
SSE gets event ids, reconnection and resume from the protocol rather than from
application code.

Fan-out is a poll of `domain_events`, scoped to the caller's organisation, once
a second. This is the part that looks like a compromise and is not:

- The worker already writes its events to that table, so worker-to-browser
  propagation crosses processes with **no broker at all**.
- A reconnecting client resumes from durable history, not from whatever a
  pub/sub channel still happened to hold. Pub/sub forgets; a table does not.
- There is no second system that can be up while the first is down, so there is
  no degraded mode in which the stream lies about what happened.

Valkey pub/sub would cut the latency floor from ~1s to ~10ms and remains a
sound optimisation. It would be an accelerator over this table, never a
replacement for it — precisely because the durability argument above does not
change.

### The stream is never the source of truth

Frames say *what changed*, never *what the new state is*. The browser refetches
through the same API every other part of the console uses, so there is one path
data can arrive by. Turning the stream off changes how quickly the console
notices things, never what it shows.

Events are written into the producer's transaction, like outbox jobs, so the
stream cannot announce an alert that then rolls back.

## Consequences

**Good.** Shared rate limiting works out of the box, with no new infrastructure
and no new failure mode for an operator to learn. The live channel needs
nothing that is not already running. A tenant's events are isolated by the same
`organization_id` predicate as everything else, and a revoked session stops
receiving within 30 seconds because the stream re-checks rather than trusting
its connect-time authorisation.

**Costs.** One indexed query per connected browser per second — fine for an
operations console, and the reason the poll interval is a named constant rather
than a literal. Live latency has a one-second floor. `rate_limit_counters`
accumulates one row per (caller, endpoint, window) until the worker prunes it;
if the worker is down the table grows, which is visible in `/health` because
the queue backlog is visible there too.

**Objective thresholds for revisiting.** Move rate limiting to Valkey when a
counter UPSERT per request is a measurable share of request latency — the
`burst` load scenario measures exactly this. Add Valkey pub/sub as a wake
signal for the stream when sub-second live latency becomes a stated
requirement, or when concurrent stream count makes the poll query a visible
share of database load (`scripts/run_load_profile.py --scenario stream`
measures that).

## Alternatives considered

**PostgreSQL `LISTEN`/`NOTIFY` for fan-out.** Genuinely elegant, and would give
near-instant delivery with no broker. Rejected for now because it needs a
dedicated connection per listener held outside the pool, and the sync
SQLAlchemy session model would have to grow an async escape hatch to use it.
Polling reaches the same place with code that is obviously correct;
`LISTEN`/`NOTIFY` is the natural next step if the one-second floor ever matters.

**WebSockets.** Bidirectional, and nothing here needs a client to send
anything. It would mean writing reconnection, resume and heartbeat by hand —
all of which SSE specifies.

**Fail-closed when the shared limit store is down.** Considered and rejected:
refusing telemetry because a rate-limit counter is unreachable converts a
dependency outage into data loss. Falling back to per-process counting keeps
the control in force at a known, reported cost.
