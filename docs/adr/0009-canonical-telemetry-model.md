# ADR 0009 — A canonical resource and dimensional metric model

- **Status:** Accepted
- **Date:** 2026-08-22
- **Supersedes in part:** the `system_metrics` fixed-column model (retirement path below)

## Context

SentinelX assumed every observable thing was a `Device` with a CPU percentage, a
memory percentage and a disk percentage. That assumption is baked into a table
whose columns *are* the metric names:

```
system_metrics(device_id, cpu_percent, memory_percent, disk_percent,
               battery_percent, battery_charging, ..., latency_ms)
```

It is true of a laptop and false of everything else. Three concrete problems
followed from it:

1. **A new metric means a schema migration.** The mobile sprint added seven
   columns for battery and network. The next metric would add more. There is no
   version of that which scales.
2. **There is nowhere to put a service.** An OTLP payload describing
   `service.name=checkout` has no `cpu_percent`, and a service is not a machine.
   The model had no way to represent it at all.
3. **There are no dimensions.** Two disks on one host cannot both be
   `disk_percent`. Neither can two network interfaces, or per-route latency.

A fourth problem was invisible until we looked for it: nothing bounded how much
telemetry a tenant could create. With fixed columns that did not matter, because
the row count was the only thing that could grow. Any dimensional model makes it
matter enormously.

## Decision

**A three-table canonical model, filled by dual-write, with the legacy table
kept authoritative until its readers move.**

### The model

```
resources        an observable thing, identified by OpenTelemetry-style
                 attributes rather than by a hostname column
metric_series    resource + metric name + unit + kind + canonical attributes
metric_points    a narrow (recorded_at, series_id, value) append table
```

Identity comes from `identifying_attributes`, split from merely descriptive
attributes by the rules in `app/services/telemetry_identity.py`. An OS patch
level changing does not create a second machine; a `service.name` changing does
create a second service.

We use the OpenTelemetry resource semantic conventions (`host.name`,
`service.name`, `deployment.environment.name`) rather than inventing names,
because an OTLP client that already sets them is then understood with no
configuration at all.

### Hashing is an accelerator, never a proof

`identity_hash` and `series_hash` make lookup an index seek. They are never
treated as evidence that two attribute sets are equal: every lookup fetches the
rows sharing a hash and compares the stored JSONB for exact equality, and
`collision_seq` keeps two genuinely different attribute sets apart if they ever
hash alike. SHA-256 makes that branch unreachable in practice. The point is that
correctness does not *depend* on it being unreachable, and a forced-collision
test proves the branch works.

### Encoding is injective, not merely hashed

The hash is computed over a length-prefixed encoding of sorted key/value pairs,
not `str(dict)` or JSON. Without length prefixes, `{"a.b": "c"}` and
`{"a": "b.c"}` serialise identically and two unrelated resources silently become
one. Values carry a type tag so the string `"1"` and the integer `1` remain
different dimensions.

### Cardinality is bounded, and the bound is on creation

A per-tenant budget on *new* series per window, not on request volume.

This is the shape of the actual failure. Someone adds a request id as an
attribute; every sample becomes its own series; the request rate is completely
normal, so rate limiting cannot see it, and the first symptom is a full disk.
Budgeting creation means an established tenant with a hundred thousand series
ingests at full speed, while runaway creation stops with a reason the operator
can act on.

Limits reject rather than truncate. Dropping the 33rd attribute would change
what a series *means* while still accepting it, and nobody would ever learn the
instrumentation was wrong.

### Units are declared, not converted

OpenTelemetry's `system.cpu.utilization` is a ratio in 0..1. SentinelX has
always collected and alerted on 0..100 percentages. Silently rescaling would
make every existing alert threshold wrong by two orders of magnitude, so the
name follows the convention and the unit is declared honestly as `"%"`.

Because unit participates in series identity, an OTLP client sending the
conventional ratio form lands in a *different* series rather than being averaged
into the same one. The ambiguity resolves itself instead of corrupting an
average.

## Alternatives rejected

**Add more columns.** Where this started. Does not represent a service, cannot
express dimensions, and every metric costs a migration.

**One JSONB blob per sample.** No series identity, so cardinality is unbounded
and unmeasurable, and every query becomes a full scan with JSONB extraction.

**Replace `system_metrics` outright.** Alert rules, the AI feature windows, the
device detail page and the hybrid detection engine all read it. A cutover would
have meant rewriting all of them in the same change, with no way to verify the
new store held correct data first.

## Retirement path for `system_metrics`

Deliberately staged, and the ordering is the point — dual-write, then move
readers, then retire the writer, so no feature ever reads from a store nothing
has populated.

1. **v3.3 (this sprint) — dual-write.** Native samples land in `system_metrics`
   as before *and* project into `metric_points` in the same transaction.
   `system_metrics` stays authoritative. Kill switch:
   `CANONICAL_TELEMETRY_DUAL_WRITE_ENABLED`.
2. **Next — move readers.** The metric query API, feature windows and the device
   detail page read canonical series. Each move is independently verifiable
   against the dual-written data.
3. **Then — stop writing the legacy table**, once no reader remains. Alert rules
   are the last and hardest, because thresholds are expressed against
   `cpu_percent` as a column.
4. **Finally — drop it**, after a release in which nothing wrote to it.

The projection runs inside a SAVEPOINT and its failure is logged rather than
raised, precisely because it is secondary during stage 1. A bug in the new
representation must not start rejecting telemetry from a fleet of working
agents. That tolerance is removed at stage 3, when it stops being secondary.

## Consequences

- A new metric is a row, not a migration.
- Services, applications, containers and embedded nodes are representable.
- Cardinality is a countable, enforceable quantity for the first time.
- Two representations exist during the transition — a real cost, accepted
  because the alternative was a flag-day rewrite of every reader at once. The
  stages above are what stop it becoming permanent.
- Storage per sample is higher than a fixed-column row (a UUID series reference
  and a timestamp per value, rather than three values sharing one row). Measured
  and accepted; see ADR 0010.
