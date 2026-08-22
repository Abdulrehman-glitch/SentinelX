# ADR 0007 — Naming and versioning the agent protocol

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Since v3.0, three agents and a bridge have spoken a wire protocol that had no
name, no version and no specification. It worked, and it was tested — 34
contract tests pinned the payload shapes — but two questions had no answer:

1. *Is this agent build compatible with this backend?* The only way to find out
   was to read both sides of the code.
2. *Is this change breaking?* Every encoding was an unwritten contract, so the
   answer depended on who you asked.

v3.3 makes substantial changes underneath the ingest path — canonical
dual-write, an outbox, a worker. Making those changes against an unnamed
contract is how a working fleet gets broken by accident.

## Decision

**Name it, version it on four independent axes, and make the specification
executable.**

### Four axes, not one

| Axis | Value | Changes when |
|---|---|---|
| Platform version | `3.3.0` | Any release |
| API version | `v1` | A breaking REST change |
| Agent Protocol version | `1.0` | Enrolment/auth/telemetry/command semantics change |
| Telemetry schema version | `1.1` | A metric payload field is added or removed |

Conflating these is the specific mistake this ADR prevents. Under a single
version number, the mobile sprint's nullable battery fields would have looked
like a breaking change to every desktop agent, and every platform release would
have implied agents needed rebuilding. Separating them means a nullable field is
a schema bump that costs nobody anything.

### The specification is executable

Three layers, each checking the one above:

- `docs/protocol/agent-protocol-v1.md` — prose.
- `backend/app/protocol.py` — the versions and the compatibility matrix in code.
- `tests/contract/test_agent_protocol_v1.py` — asserts the code against the live
  endpoints.

Prose drifts. A document that claims `/v1/metrics` exists is worthless if the
route was renamed, so a test posts to it and requires a `401` rather than a
`404`. A document that says logs are unsupported is worthless if someone ships
logs and forgets the doc, so a test requires `protocol.otlp.logs` to be `null`.

`GET /api/v1/health` returns the whole matrix, so a client can check
compatibility before committing rather than discovering it at runtime.

### Missing version headers are accepted

Every shipped agent predates the header and speaks exactly `1.0`. Rejecting them
would break working deployments in order to enforce a label they were never
asked for, which is the opposite of what versioning is for.

### iOS is listed but not canonical

It speaks the same wire format. It is not covered by these contract tests, and
its migration belongs to the Fleet sprint. Listing it as canonical would claim
coverage nothing backs — and the matrix says `canonical: false` explicitly
rather than omitting it, because an integrator needs to know it exists.

## Consequences

- "Will this break the agents?" is answerable by running a test suite.
- Additive telemetry changes stop looking like protocol changes.
- The documented capability surface cannot silently overstate itself.
- Four version numbers is more bookkeeping than one. Accepted: the alternative
  is one number that lies about at least three things.
- v3.3 shipped without changing a single agent-visible field, which is what made
  it safe to change everything underneath.
