# ADR 0010 — PostgreSQL for telemetry storage, and when to stop

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Introducing a series/point model (ADR 0009) means one table will grow far faster
than anything else in SentinelX. The obvious question is whether PostgreSQL is
the right home for it, or whether a purpose-built time-series store —
TimescaleDB, ClickHouse, InfluxDB — is warranted.

That question is usually answered with folklore. We answered it by measuring,
because adding a second database is very hard to reverse: another service to
run, another backup story, another consistency boundary, and a permanent split
in where the truth lives.

## Decision

**PostgreSQL, unpartitioned, with a deliberate index set. Revisit at a measured
threshold, not a feeling.**

### Measured baseline

`scripts/benchmark_metric_storage.py`, 500,000 points across 200 series spread
over ~30 days of timestamps.

```
host      : AMD64 Family 25 Model 80 (Ryzen) / Windows
postgres  : 18.4
python    : 3.12.10
```

| | |
|---|---|
| Insert throughput | **17,938 points/sec** (5,000-row batches, one connection) |
| Batch latency p50 / p95 / p99 | 274.9 / 315.9 / 321.9 ms |
| Heap size | 48.3 MiB — **101 bytes/point** |
| Index size (all) | 106.6 MiB |
| BRIN on `recorded_at` | **24 KiB** |
| B-tree on `(series_id, recorded_at)` | 33.8 MiB |

Query plans, `EXPLAIN (ANALYZE, BUFFERS)`:

| Query | Plan | Execution |
|---|---|---|
| One series, last hour (dashboard) | Bitmap index scan on `(series_id, recorded_at)` | **0.060 ms** |
| One series, 5-min buckets over 24h (chart) | Bitmap index scan + GroupAggregate, 87 rows | **0.204 ms** |
| Whole tenant, 7-day scan (retention/export) | **BRIN** + parallel bitmap heap scan | **59.9 ms** |

### What the numbers say

**Throughput is not the constraint.** 17,938 points/sec is roughly *1,300 times*
SentinelX's current native load — a fleet of 100 devices at one sample per 15
seconds produces about 13 points/sec across three metrics. The gap is four
orders of magnitude. Choosing a specialist database for write throughput we do
not need, at the cost of a second system to operate, would be optimising the
wrong variable by a very large margin.

**BRIN earns its place decisively.** 24 KiB versus 33.8 MiB for the B-tree —
1,441× smaller — and the planner genuinely chooses it for the tenant-wide time
scan rather than ignoring it. That is the append-correlated access pattern BRIN
exists for, and retention deletes and exports both take that path.

**Indexes cost more than the data.** 106.6 MiB of index against 48.3 MiB of
heap. That is the honest finding of this exercise and the thing to watch: the
`(recorded_at, id)` primary key is expensive because a random UUID compresses
badly, and `(series_id, event_id)` exists only for native-agent idempotency
while being NULL for every OTLP point. If storage becomes a problem before
throughput does — which these numbers suggest it will — that is where to look
first, well before reaching for another database.

### Partitioning: designed for, not yet applied

`metric_points` is **not** partitioned today. At this scale it would add
maintenance (creating and dropping partitions) and planning overhead to solve a
problem that does not exist yet: a 48 MiB heap does not need pruning.

What *is* done is making the change cheap later. The primary key is
`(recorded_at, id)`, not `id`. Postgres requires the partition key to appear in
every unique constraint, so leading with `recorded_at` means introducing
`PARTITION BY RANGE (recorded_at)` is a migration rather than a full table
rewrite — the expensive part is already paid.

**Measured trigger to partition, monthly:** any of

- `metric_points` heap exceeding **20 GiB**, or
- the 7-day tenant scan exceeding **2 seconds** (about 30× today's 59.9 ms), or
- retention deletes holding locks long enough to affect ingest latency.

Partitioning also changes idempotency: a unique constraint must include the
partition key, so `(series_id, event_id)` cannot remain global. The replacement
is a separate dedupe table with a bounded window, which is a better design
anyway — deduplicating against all history forever is not something anyone
needs.

## Alternatives rejected, and what would change our mind

**TimescaleDB.** The natural choice, and genuinely good. Rejected for now
because it is an extension the deployment must have — which conflicts directly
with running on plain Postgres 16 in CI and Postgres 18 locally, with no
guarantee about what a future host offers. Its compression is the compelling
feature, and given that indexes already outweigh the heap, it is the first thing
to reconsider if storage becomes the binding constraint.

**ClickHouse.** Enormously faster for analytical scans and the wrong shape here.
It is a second database, so telemetry and the relational data it must join
against (devices, alerts, incidents, organisations) end up in different systems
with no transactional boundary between them. The transactional outbox in ADR
0008 depends on telemetry and its processing obligations committing together;
that guarantee does not survive the split.

**InfluxDB.** Same second-database objection, plus a query language nothing else
in the stack speaks.

**A cloud-managed time-series service.** Hosting is paused (ADR 0003).

The honest summary: PostgreSQL is not merely adequate here, it is *comfortable*
— by four orders of magnitude on writes and by three on the queries the
dashboard issues. The trigger conditions above are what would reopen this, and
they are numbers rather than opinions.

## Consequences

- One database. One backup, one restore, one consistency boundary, one thing to
  operate.
- Telemetry can be joined to devices, alerts and incidents in a single query.
- Storage per point is higher than a specialist columnar store would achieve.
  Accepted, and quantified above rather than guessed at.
- The partitioning decision is deferred but not blocked, and the threshold that
  would force it is written down.
- `scripts/benchmark_metric_storage.py` is committed, so the next person can
  re-measure on their own hardware instead of trusting this table.
