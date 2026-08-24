# ADR 0008 — A transactional outbox and an in-project worker

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Every downstream consequence of ingesting a metric happened inside the HTTP
request that delivered it: alert-rule evaluation, incident creation, audit
writes, and — on the AI path — feature-window construction that re-reads raw
`system_metrics`. An agent's POST paid for all of it.

Two things were wrong with that.

**Latency belongs to the agent.** The slowest work in the request had nothing to
do with storing the sample.

**`session_service.purge_expired_sessions()` existed and nothing called it.**
Written during the v3.2 session work, correct, tested, and never scheduled. Rows
accumulated forever. There was no mechanism to run periodic work at all, so it
was not an oversight so much as a missing capability.

The obvious fix — publish a message and return — introduces a failure this
system must not have:

```
1. telemetry commits
2. queue publication fails
3. the required downstream processing silently disappears
```

That window is unacceptable for alerting. A sample that should have raised a
critical alert must not be able to vanish because a broker was briefly
unreachable.

## Decision

**A transactional outbox in PostgreSQL, drained by an in-project worker.**

### The outbox

`enqueue()` writes an `outbox_jobs` row into the **caller's open transaction**
and does not commit. The telemetry and the obligation to process it therefore
become durable together, or neither does. A version of this that opened its own
session would reintroduce exactly the window above.

This is the one property that makes the whole design worth its complexity, and
it is asserted directly: a test rolls back the caller's transaction and requires
the job to have vanished with it.

### The worker

`python -m app.worker`. Claims with `SELECT ... FOR UPDATE SKIP LOCKED`, so
several workers drain concurrently without coordinating and none waits behind
another's row. One transaction per job: the handler's writes and the job's
status change commit together.

Handlers must be idempotent, because delivery is at-least-once. Making it
exactly-once needs distributed consensus; making handlers re-runnable needs a
paragraph of care each. We chose the paragraph.

### Attempts count at claim time, not at failure

This looks like a bug until you see what it prevents. A job that segfaults the
worker, exhausts its memory, or wedges it never reaches a failure handler — so a
failure-time counter stays at zero and the job is retried forever, killing every
worker that touches it. Counting at claim time means such a job burns through
`max_attempts` and lands in `dead` like any other. Poison-job isolation without
needing to classify the poison.

### Maintenance needs no leader

A periodic job is enqueued with a dedupe key containing its time bucket
(`maintenance.prune_outbox:<bucket>`). Every worker computes the same key, all
of them try to insert it, and the unique constraint picks exactly one winner.

That is leader election for free: no lease to renew, nothing to go stale, no
split-brain, and it works with one worker or ten.

`purge_expired_sessions` is now scheduled hourly, alongside outbox and
domain-event pruning.

## Alternatives rejected

**Celery.** Popular, and the wrong shape here. Needs a broker (a new
availability dependency and a second thing to operate), and on the owner's
Windows development machine it needs installing and supervising, where
`python -m app.worker` just runs. It would buy throughput SentinelX does not
need at the cost of the durability property above, unless we ran an outbox in
front of it anyway — at which point Celery is the redundant part.

**ARQ.** Async-native, which fits FastAPI and not this codebase: the application
is synchronous SQLAlchemy on psycopg throughout. Adopting it means either
rewriting the data layer or running sync code on an event loop.

**Redis/Valkey as the queue.** Valkey's role is deliberately limited to
ephemeral coordination. A queue in Valkey is a queue that can lose
correctness-critical work on eviction or restart, and telemetry processing
obligations are correctness-critical.

**`LISTEN`/`NOTIFY` for wakeups.** Attractive — it would replace polling. Not
adopted yet because notifications are lost if no listener is connected, so it is
an optimisation on top of polling rather than a replacement for it. Worth
revisiting when idle latency actually matters.

## What moved, and what deliberately did not

**Moved:** feature-window construction, coalesced per device per five-minute
bucket, so a device sampling every 15 seconds enqueues one job every few minutes
rather than one per sample. This was the genuinely expensive work — it re-reads
raw samples.

**Deliberately not moved:** alert-rule evaluation on `/api/v1/metrics`. The
response carries `alerts_created`, which is part of the pinned agent wire
contract, and making it asynchronous would either break that field or make it a
lie. The evaluation itself is a handful of indexed queries, not the expensive
part. Moving it would be a protocol change wearing a performance costume.

## Consequences

- No window exists in which telemetry commits and its processing disappears.
- Periodic maintenance runs at all, for the first time.
- Queue depth and oldest-job age are observable, and feed both `/health`
  degradation and OTLP load shedding.
- The worker is a second process to run. Accepted: it is one command, it needs
  no configuration, and the API keeps functioning without it — work simply
  queues up, which is visible in `/health` rather than silent.
- Polling means idle latency of up to `--idle-sleep` seconds. Acceptable for
  every job type here; none is interactive.
