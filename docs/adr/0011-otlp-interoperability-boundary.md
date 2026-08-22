# ADR 0011 — Where OTLP support starts and stops

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

"Supports OpenTelemetry" is a claim that costs an integrator an afternoon when
it is vague. OTLP covers three signals (metrics, logs, traces), two transports
(gRPC, HTTP), two encodings (protobuf, JSON) and several point kinds. A product
that implements one corner and advertises the family is worse than one that
advertises nothing, because the failure surfaces after someone has already
committed to it.

SentinelX needed real interoperability — an existing OpenTelemetry deployment
should be able to send metrics without writing a SentinelX-specific exporter —
without pretending to a scope it does not have.

## Decision

**Implement OTLP/HTTP metrics properly. Advertise exactly that, machine-readably.**

### Implemented

| | |
|---|---|
| Signal | Metrics |
| Transport | HTTP/1.1 |
| Encoding | `application/x-protobuf` |
| Path | `POST /v1/metrics` |
| Compression | none, gzip |
| Point kinds | Gauge, Sum (delta and cumulative) |
| Partial success | Yes |
| Error bodies | `google.rpc.Status` |

Generated from the official `opentelemetry-proto` package, never a hand-written
schema. A hand-rolled approximation of a wire format is a bug waiting for a
client that uses a field you skipped.

### Not implemented, and advertised as absent

OTLP logs, OTLP traces, gRPC transport, OTLP/JSON, histograms, exponential
histograms, summaries.

`GET /api/v1/health` returns `protocol.otlp.logs = null` and
`protocol.otlp.traces = null` — not `"planned"`, not omitted. A contract test
asserts those nulls, so shipping logs support without updating the
advertisement fails CI.

A histogram data point is rejected with `unsupported_metric_type` and a message
naming the kind, rather than being silently dropped. A client that sends one
learns immediately; silence would let it believe the data arrived.

### Why the path is `/v1/metrics` and not `/api/v1/otlp/metrics`

Every OTLP exporter appends `/v1/metrics` to its configured endpoint. Serving it
anywhere else means every client needs a path override, and OTLP support that
requires bespoke configuration is not really OTLP support. The path sits outside
SentinelX's `/api/v1` prefix for exactly that reason.

### Why gRPC is not implemented

It would add a second server, a second port, and a second set of streaming
semantics for the same signal SentinelX already accepts. The Collector
translates gRPC to OTLP/HTTP as a matter of course, so an SDK already configured
for gRPC reaches SentinelX through a Collector with no application change. The
compose profile demonstrates precisely that path.

### Why OTLP/JSON is not implemented

It is a legitimate encoding and would be straightforward. It is not implemented
because it is not yet needed, and a `Content-Type` of `application/json` returns
`415` with a message saying so, rather than being accepted and mis-parsed.

## Security decisions

**A separate credential type.** An ingest key (`sxi_live_`) is
organisation-scoped and is not a device token. A device token identifies one
machine; letting one authenticate OTLP would let a compromised agent write
telemetry for arbitrary resources. A contract test asserts a device token is
rejected on `/v1/metrics`.

**The tenant comes from the credential, never the payload.** A resource
attribute claiming another organisation is just an attribute, and `sentinelx.*`
attributes from an untrusted client are stripped before identity is derived.

**SHA-256 rather than argon2 for the key.** Argon2 makes *guessable* secrets
expensive by being slow. These keys are 32 bytes of `secrets.token_urlsafe`;
there is no dictionary and the search space is the defence. A fast hash also
allows one indexed lookup rather than verifying a slow hash against every
credential — the amplification that forced legacy device tokens to be disabled.

**Decompression is bounded during inflation.** A few hundred kilobytes of gzip
can inflate to gigabytes, so a size check after decompressing is a check after
the memory is already allocated. `safe_gunzip` uses `decompressobj`'s
`max_length` and detects a bomb by there being input left over.

## Consequences

- An existing OpenTelemetry deployment can send metrics to SentinelX today,
  through the reference Collector, with no custom code.
- The advertisement is machine-readable and test-enforced, so it cannot drift
  into overstatement.
- Adding logs or traces later is additive: new endpoints, new scopes on the
  existing credential model, no change to what exists.
- Histogram-heavy instrumentation is partially rejected. Correct for now —
  storing a histogram as a number would be worse than refusing it.
