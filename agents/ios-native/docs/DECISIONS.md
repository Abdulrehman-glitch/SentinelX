# SentinelX Mobile Agent Decisions

This log records implementation decisions that affect simulator, server, or
mobile-agent behaviour.

## ADR-001 - Deterministic Simulator Payload Curves

Status: accepted

Date: 2026-07-06

Context: C0 requires plausible payload generators for the five core telemetry
categories before the dev server is fully handed off. Tests need repeatable
payloads while simulator runs still need realistic drift and state changes.

Decision: Use a small stateful `PayloadGenerator` backed by Python's standard
`random.Random`. Battery, thermal, network, and storage values are generated
from deterministic sequence-based curves, with seeded jitter only where it makes
the payload look less artificial. Event IDs remain fresh UUIDs because
idempotency tests must exercise real unique event identifiers.

Consequences: Tests can compare payloads and timestamps exactly when using the
same seed, while callers still receive valid unique event envelopes. The curves
are intentionally simple and can be tuned later without changing the public
function names.
