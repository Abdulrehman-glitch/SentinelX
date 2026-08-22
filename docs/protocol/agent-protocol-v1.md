# SentinelX Agent Protocol v1

- **Status:** Stable
- **Protocol version:** `1.0`
- **Telemetry schema version:** `1.1`
- **Introduced:** v3.3 (2026-08-22)

This document describes a protocol that has existed since v3.0. Three agents and
a bridge have been speaking it, and nothing here changes a single byte on the
wire. What changes is that it now has a name, a version, and
`tests/contract/test_agent_protocol_v1.py` asserting that this document is true.

Before this, any change to an encoding was a change to an unwritten contract,
and nobody could answer "is this agent build still compatible?" without reading
both sides of the code.

---

## 1. Version axes

Four numbers, deliberately independent. Conflating them is the failure this
section exists to prevent.

| Axis | Value | Changes when |
|---|---|---|
| Platform version | `3.3.0` | Any SentinelX release. Cosmetic to agents. |
| API version | `v1` (`/api/v1` prefix) | A breaking REST change. Has not happened. |
| **Agent Protocol version** | **`1.0`** | Enrolment, auth, telemetry or command *semantics* change. |
| Telemetry schema version | `1.1` | A metric payload field is added or removed. |

A platform release does not force a protocol bump. Adding a nullable telemetry
field is a schema change, not a protocol change — which is exactly why the
mobile battery/network fields in `1.1` did not break `1.0` desktop agents.

The authoritative copy of these values is `backend/app/protocol.py`; this table
is checked against it by a contract test.

### Client compatibility matrix

| Component | Version | Protocol | Telemetry schema | Canonical |
|---|---|---|---|---|
| `agents/desktop-python` | 3.0.0 | 1.0 | 1.1 | **Yes** |
| `agents/android-native` | 3.0.0 | 1.0 | 1.1 | **Yes** |
| `agents/embedded-bridge` | 3.0.0 | 1.0 | 1.1 | **Yes** |
| `agents/ios-native` | 1.0.0 | 1.0 | 1.0 | No — Fleet sprint |

"Canonical" means this sprint guarantees and tests the client. iOS speaks the
same wire format and is not expected to break, but it is not covered by these
contract tests and must not be described as if it were.

---

## 2. Identity

Three distinct identities, which are not interchangeable:

- **Device identity** — a `Device` row, `UUID`, one physical or virtual machine
  in one organisation. Unique by `(hostname, organization_id)`.
- **Agent identity** — the software on that device: `agent_type` (e.g.
  `python_desktop_agent`) and `agent_version`. Several agent versions may report
  for the same device over its lifetime.
- **Resource identity** *(new in v3.3)* — the canonical entity in `resources`.
  For an agent-managed device this is pinned by `sentinelx.resource.id`, so
  **renaming a host does not create a second resource**. See
  `docs/adr/0009-canonical-telemetry-model.md`.

---

## 3. Enrolment

An agent has no credential until it enrols, and enrolment requires a short-lived
code an administrator minted.

```
POST /api/v1/devices/enrollment-codes   (admin session) -> { "code": "..." }
POST /api/v1/devices/enroll             (no auth)       -> { "device": {...}, "device_token": "sxa_..." }
```

The device token is returned **once**. Only a hash is stored, so a lost token
means re-enrolment or rotation, never recovery.

Enrolment is idempotent by `(hostname, organization_id)`: an agent reinstalled
on the same machine re-attaches to the existing device rather than creating a
duplicate.

---

## 4. Authentication

Every agent call carries the device token:

```
Authorization: Bearer sxa_<credential-id-hex>.<secret>
```

The `sxa_` prefix embeds the credential id so resolution is one indexed lookup
rather than an argon2 verification against every active credential — the
amplification that made pre-v2 opaque tokens a denial-of-service vector. Legacy
opaque tokens stay disabled unless `ALLOW_LEGACY_DEVICE_TOKENS` is set.

A device token authenticates **one device**. It is not an ingest credential and
cannot be used on `/v1/metrics` (see §10).

---

## 5. Heartbeat

```
POST /api/v1/heartbeats
```

Sets `last_seen_at` and `status`. Independent of the telemetry interval, so a
device with nothing to report is still visibly alive.

---

## 6. Telemetry submission

### Single sample

```
POST /api/v1/metrics
{
  "device_id": "<uuid>",           // must match the token's device
  "event_id":  "<uuid>|null",      // idempotency key, optional
  "cpu_percent":    0-100 | null,  // null means "could not read", never 0
  "memory_percent": 0-100,
  "disk_percent":   0-100,
  ...schema 1.1 mobile extras, all nullable
}
->  201 { "metric": {...}, "alerts_created": <int>, "duplicate": <bool> }
```

`device_id` mismatching the token is `403`. This is what stops a compromised
agent writing telemetry for another device or tenant.

### Batch

```
POST /api/v1/metrics/batch
{ "device_id": "<uuid>", "samples": [ {..., "recorded_at": "<iso8601>"}, ... ] }   // 1..500
->  201 { "stored": <int>, "duplicates": <int>, "alerts_created": <int>, "latest": {...} }
```

Batch semantics that matter:

- **Client timestamps are preserved.** A queue flushed after an offline window
  lands as real history, not a burst at "now".
- **A future `recorded_at` is clamped to now.** A fast client clock must not
  write the future into history.
- **Alert rules evaluate only the newest sample.** A backlog describes the past;
  firing an alert per stale sample would be a storm, not information.

### Idempotency

`event_id` is the client's key. A retry after a lost response is acknowledged
(`duplicate: true`) rather than stored twice, enforced by a unique constraint on
`(device_id, event_id)` — the database is the backstop, not the application
check. Omitting `event_id` is legal and disables deduplication for that sample.

---

## 7. Command polling and acknowledgement

```
GET  /api/v1/agent/commands            -> pending signed commands
POST /api/v1/agent/commands/{id}/ack   -> state transition
```

Commands are Ed25519-signed over a canonical payload. The agent verifies the
signature before executing and rejects anything past `expires_at`.

The canonical signed payload deliberately duplicates `expires_at`. That is not a
mistake and is pinned by a contract test: changing it is an incompatible
protocol change requiring a coordinated agent bump.

### Command states

```
pending -> sent -> acknowledged -> started -> completed
                                          \-> failed
                \-> rejected                  (agent refused: unknown action,
                                               capability missing, expired)
```

`rejected` and `failed` are different facts. Rejected means the agent declined
before doing anything; failed means it tried and the operation did not succeed.
Recovery results carry structured output, never free-form shell output — agents
execute a narrow allowlist, never arbitrary commands.

---

## 8. Capability reporting

An agent reports what it can actually do (`agent_capabilities`). The server
refuses to issue a command an agent has not declared support for, so a policy
mistake surfaces as a rejected command rather than an ignored one.

---

## 9. Error envelope

All agent-facing errors are the standard FastAPI JSON shape:

```json
{ "detail": "human readable reason" }
```

with `X-Request-ID` echoed on every response for correlation.

| Status | Meaning for an agent |
|---|---|
| `400` | Malformed request. Do not retry unchanged. |
| `401` | Token missing, unknown or revoked. Re-enrol or rotate. |
| `403` | Authenticated but not permitted (e.g. `device_id` mismatch). Do not retry. |
| `422` | Validation failure. Do not retry unchanged. |
| `429` | Rate limited. Back off and retry. |
| `503` | Overloaded or shedding. Honour `Retry-After`. |

`400`, `403` and `422` are permanent for that payload; retrying is a bug.
`429` and `503` are temporary and must be retried with backoff.

---

## 10. Relationship to OTLP

OTLP is a **separate** ingestion path with a **separate** credential type.

| | Agent Protocol v1 | OTLP |
|---|---|---|
| Path | `/api/v1/metrics` | `/v1/metrics` |
| Credential | Device token (`sxa_`) | Ingest key (`sxi_live_`) |
| Scope | One device | One organisation |
| Encoding | JSON | Protobuf |

They are not interchangeable in either direction, and a contract test asserts
that a device token is rejected on `/v1/metrics`.

---

## 11. Compatibility policy

1. **Additive changes do not bump the protocol.** A new nullable field is a
   telemetry schema bump; old agents keep working.
2. **An agent that sends no version header is treated as `1.0`.** Every shipped
   agent predates the header and speaks exactly that. Rejecting them would break
   working fleets to enforce a label they were never asked for.
3. **Removing or repurposing a field is a protocol bump**, and requires the
   server to accept both versions for at least one release.
4. **The signed command payload is frozen.** Changing it — including its
   duplicated `expires_at` — requires a coordinated agent release.
5. **Deprecation is announced through `/api/v1/health`** before removal, so a
   client can detect it without reading a changelog.

---

## 12. What v3.3 did *not* change

Deliberately, so that no canonical agent needs rebuilding:

- No request or response field was added, removed or renamed.
- No status code changed.
- No authentication mechanism changed.
- Canonical dual-write into `metric_points` happens server-side and is invisible
  to agents.
- Feature-window construction moved to a background worker, which changes *when*
  the work happens, not what any agent sees.
