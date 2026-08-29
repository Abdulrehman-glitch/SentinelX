"""SentinelX Agent Protocol v1 — the versions, in code.

Everything here already existed as behaviour; what was missing was a name and a
number for it. Three agents and a bridge have been speaking this protocol
informally since v3.0, which meant a change to any encoding was a change to an
unwritten contract, and nobody could say whether a given agent build was still
compatible.

The point of this module is that the version matrix is *executable*. The
documentation in docs/protocol/agent-protocol-v1.md describes it in prose, and
tests/contract/test_agent_protocol_v1.py asserts these constants against the
real endpoints, so the prose cannot quietly drift away from the software.

Four version numbers, deliberately distinct. Conflating them is the mistake
this module exists to prevent:

  platform version   SentinelX as a product (3.3.0). Marketing-facing.
  API version        the /api/v1 URL prefix. Changes only on a breaking REST
                     change, which has not happened.
  protocol version   how an agent enrols, authenticates, sends telemetry and
                     executes commands. This is the one agents care about.
  telemetry schema   the shape of a metric payload. Moves independently of the
                     protocol: adding a nullable field is a schema change, not
                     a protocol change.

A component can therefore ship a new agent version without touching the
protocol, and the protocol can gain a capability without forcing every agent to
upgrade at once.
"""

from __future__ import annotations

from dataclasses import dataclass

# The protocol this backend implements.
AGENT_PROTOCOL_VERSION = "1.0"

# Protocol versions this backend still accepts. Pre-v1 agents predate the
# formalisation and are treated as "1.0" — the wire format is unchanged, so
# refusing them would break working fleets to enforce a label.
SUPPORTED_PROTOCOL_VERSIONS = ("1.0",)

# The shape of a metric payload. Bumped when a field is added or removed, which
# is independent of whether the protocol itself changed.
TELEMETRY_SCHEMA_VERSION = "1.1"
SUPPORTED_TELEMETRY_SCHEMA_VERSIONS = ("1.0", "1.1")

# Optional header. An agent that sends it gets an explicit compatibility answer;
# an agent that does not is assumed to speak 1.0, which every shipped agent does.
PROTOCOL_VERSION_HEADER = "X-SentinelX-Protocol-Version"


@dataclass(frozen=True)
class ClientCompatibility:
    """One client's position in the matrix.

    `canonical` marks the clients this sprint guarantees. iOS is deliberately
    excluded: it speaks the same wire format, but its migration is Fleet-sprint
    work and pretending otherwise would claim coverage no test backs.
    """

    component: str
    version: str
    protocol: str
    telemetry_schema: str
    canonical: bool
    notes: str


COMPATIBILITY_MATRIX: tuple[ClientCompatibility, ...] = (
    ClientCompatibility(
        component="agents/desktop-python",
        version="3.0.0",
        protocol="1.0",
        telemetry_schema="1.1",
        canonical=True,
        notes="Enrolment, heartbeat, single-sample telemetry, signed command execution.",
    ),
    ClientCompatibility(
        component="agents/android-native",
        version="3.0.0",
        protocol="1.0",
        telemetry_schema="1.1",
        canonical=True,
        notes="Batch telemetry with preserved client timestamps and battery/network extras.",
    ),
    ClientCompatibility(
        component="agents/embedded-bridge",
        version="3.0.0",
        protocol="1.0",
        telemetry_schema="1.1",
        canonical=True,
        notes="Forwards Arduino sensor readings to /telemetry/embedded.",
    ),
    ClientCompatibility(
        component="agents/ios-native",
        version="1.0.0",
        protocol="1.0",
        telemetry_schema="1.0",
        canonical=False,
        notes="Speaks the same wire format but is NOT canonical this sprint; "
        "full migration belongs to the Fleet sprint.",
    ),
)

CANONICAL_CLIENTS = tuple(c for c in COMPATIBILITY_MATRIX if c.canonical)


def is_protocol_supported(version: str | None) -> bool:
    """An absent version means a pre-formalisation agent, which is fine.

    Those agents send exactly the 1.0 wire format; rejecting them would break
    working deployments to enforce a label they were never asked for.
    """
    if version is None or not version.strip():
        return True
    return version.strip() in SUPPORTED_PROTOCOL_VERSIONS


def protocol_summary() -> dict:
    """What /health advertises, so a client can check before it commits."""
    return {
        "agent_protocol_version": AGENT_PROTOCOL_VERSION,
        "supported_agent_protocol_versions": list(SUPPORTED_PROTOCOL_VERSIONS),
        "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
        "supported_telemetry_schema_versions": list(SUPPORTED_TELEMETRY_SCHEMA_VERSIONS),
        "otlp": {
            # Stated precisely, because "supports OpenTelemetry" is the kind of
            # claim that wastes an integrator's afternoon when it is vague.
            "metrics": {
                "transports": ["http/protobuf"],
                "path": "/v1/metrics",
                "compression": ["none", "gzip"],
                "point_kinds": ["gauge", "sum"],
                "partial_success": True,
            },
            "logs": {
                "transports": ["http/protobuf"],
                "path": "/v1/logs",
                "compression": ["none", "gzip"],
                "partial_success": True,
                # A log line's trace_id and span_id are stored, which is what
                # makes the jump from a slow span to what it printed possible.
                "trace_correlation": True,
            },
            "traces": {
                "transports": ["http/protobuf"],
                "path": "/v1/traces",
                "compression": ["none", "gzip"],
                "partial_success": True,
                "span_events": True,
                # Stated because it is the one thing integrators check: links
                # between traces are accepted on the wire but not stored, so
                # claiming support would be a lie.
                "span_links": False,
            },
        },
    }
