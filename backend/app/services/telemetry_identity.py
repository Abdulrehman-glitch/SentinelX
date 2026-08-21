"""Turning attribute bags into stable identities.

Every telemetry payload SentinelX accepts — native agent, embedded bridge or
OTLP — eventually has to answer two questions: *which thing is this about*, and
*which measurement of it is this*. Both answers must be identical for two
payloads that mean the same thing and different for two that do not, forever,
across processes and restarts. That is what this module provides.

Three properties are load-bearing:

Determinism. The hash is computed over a length-prefixed encoding of sorted
key/value pairs, not over `str(dict)` or JSON. Python's dict repr depends on
insertion order and JSON separators vary between libraries, so either would
make the same attributes hash differently depending on how they arrived.

Unambiguity. Length prefixes matter more than they look. Naively joining with
a separator lets `{"a.b": "c"}` and `{"a": "b.c"}` produce the same byte
string; prefixing each field with its byte length makes the encoding injective,
so distinct attribute sets cannot collide by construction rather than by luck.

Honesty about hashing. `attributes_hash` is an index accelerator. It is never
treated as proof that two attribute sets are equal — callers look up by hash
and then compare the canonical dict itself. See `resource_service` and
`metric_series_service`, both of which carry a `collision_seq` for the case
where that comparison disagrees with the hash.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

# Value types an attribute may hold. OTLP also permits arrays and nested
# key-value lists; SentinelX flattens those to a textual form rather than
# inventing a nested dimension model it cannot query.
AttributeValue = str | int | float | bool

# Attributes SentinelX assigns itself. A client cannot set these — if it tries,
# the value is dropped rather than trusted, because they carry authority.
RESERVED_ATTRIBUTE_PREFIX = "sentinelx."

# An explicit identity override, set by SentinelX when it knows the resource
# corresponds to a Device it already manages.
SENTINELX_RESOURCE_ID = "sentinelx.resource.id"

# Which attributes decide *identity* rather than merely describing. Ordered by
# precedence: the first rule whose required key is present wins, and only that
# rule's keys participate in the identity. Everything else is descriptive and
# may drift freely without creating a second resource.
#
# Drawn from the OpenTelemetry resource semantic conventions rather than
# invented, so an OTLP client that already sets these is understood without
# configuration.
_IDENTITY_RULES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    # (required key, keys forming the identity, inferred resource type)
    (SENTINELX_RESOURCE_ID, (SENTINELX_RESOURCE_ID,), "host"),
    (
        "service.name",
        ("service.name", "service.namespace", "service.instance.id", "deployment.environment.name"),
        "service",
    ),
    ("container.id", ("container.id",), "container"),
    ("host.id", ("host.id",), "host"),
    ("host.name", ("host.name",), "host"),
    ("device.id", ("device.id",), "embedded_node"),
)


def coerce_value(value: Any) -> AttributeValue | None:
    """Reduce an OTLP/JSON value to something storable, or None to drop it.

    `None` is dropped rather than stored: an attribute whose value is unknown
    is not the same as an attribute whose value is the string "None", and
    letting the two merge would silently fuse distinct series.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # before int — bool is a subclass of int
        return value
    if isinstance(value, (int, float)):
        # NaN and the infinities have no stable textual identity and cannot be
        # meaningfully compared, so they are not admissible as dimensions.
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            return None
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        # OTLP array values, flattened to a deterministic textual form. Nested
        # structure is not a dimension SentinelX can query on.
        parts = [coerce_value(v) for v in value]
        return "[" + ",".join(str(p) for p in parts if p is not None) + "]"
    if isinstance(value, Mapping):
        inner = canonical_attributes(value)
        return "{" + ",".join(f"{k}={v}" for k, v in inner.items()) + "}"
    return str(value)


def canonical_attributes(raw: Mapping[str, Any] | None) -> dict[str, AttributeValue]:
    """Normalise an attribute bag into its canonical, comparable form.

    Sorted by key, empty keys dropped, unusable values dropped. Two bags that
    mean the same thing come out byte-identical.
    """
    if not raw:
        return {}

    out: dict[str, AttributeValue] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            key = str(key)
        key = key.strip()
        if not key:
            continue
        coerced = coerce_value(value)
        if coerced is None:
            continue
        out[key] = coerced

    return {k: out[k] for k in sorted(out)}


def strip_reserved(attributes: Mapping[str, AttributeValue]) -> dict[str, AttributeValue]:
    """Drop client-supplied attributes in SentinelX's own namespace.

    These carry authority (they can pin a resource identity), so a client must
    not be able to set them by simply naming them.
    """
    return {k: v for k, v in attributes.items() if not k.startswith(RESERVED_ATTRIBUTE_PREFIX)}


def _encode_field(value: str) -> bytes:
    """Length-prefixed encoding, so concatenation stays injective.

    Without the prefix, {"a.b": "c"} and {"a": "b.c"} can serialise to the same
    bytes under a naive separator join.
    """
    raw = value.encode("utf-8")
    return f"{len(raw)}:".encode("ascii") + raw


def _encode_value(value: AttributeValue) -> bytes:
    # The type tag keeps the string "1" and the integer 1 from colliding.
    if isinstance(value, bool):
        tag, text = "b", "true" if value else "false"
    elif isinstance(value, int):
        tag, text = "i", str(value)
    elif isinstance(value, float):
        tag, text = "f", repr(value)
    else:
        tag, text = "s", value
    return tag.encode("ascii") + _encode_field(text)


def attributes_hash(*parts: Any) -> str:
    """SHA-256 over a deterministic encoding of the given parts.

    Parts may be plain strings or canonical attribute dicts. Order matters and
    is the caller's responsibility — it is part of what is being identified.
    """
    digest = hashlib.sha256()
    for part in parts:
        if part is None:
            digest.update(b"n")
            continue
        if isinstance(part, Mapping):
            digest.update(b"m")
            digest.update(_encode_field(str(len(part))))
            for key in sorted(part):
                digest.update(_encode_field(key))
                digest.update(_encode_value(part[key]))
            continue
        digest.update(b"s")
        digest.update(_encode_field(str(part)))
    return digest.hexdigest()


def split_resource_identity(
    attributes: Mapping[str, Any] | None,
) -> tuple[dict[str, AttributeValue], dict[str, AttributeValue], str]:
    """Split an attribute bag into (identifying, descriptive, resource_type).

    The identifying half decides which Resource this is. The descriptive half
    can change on every payload — an OS patch level, an agent version — without
    creating a second resource for the same machine.

    If no identity rule matches, every attribute is treated as identifying.
    That is deliberately conservative: it may create more resources than an
    operator expected, which is visible and fixable, whereas guessing wrong in
    the other direction silently merges two machines into one.
    """
    canonical = canonical_attributes(attributes)

    for required, identity_keys, resource_type in _IDENTITY_RULES:
        if required not in canonical:
            continue
        identifying = {k: canonical[k] for k in identity_keys if k in canonical}
        descriptive = {k: v for k, v in canonical.items() if k not in identifying}
        return identifying, descriptive, resource_type

    return canonical, {}, "host"


def resource_identity_hash(identifying: Mapping[str, AttributeValue]) -> str:
    return attributes_hash("resource:v1", identifying)


def series_identity_hash(
    *,
    resource_identity: str,
    metric_name: str,
    metric_unit: str | None,
    metric_kind: str,
    attributes: Mapping[str, AttributeValue],
) -> str:
    """Identity of one measured thing.

    Includes the resource's identity hash rather than its database id, so the
    same series computed before and after the resource row exists agrees with
    itself, and so the value is reproducible from a payload alone.
    """
    return attributes_hash(
        "series:v1",
        resource_identity,
        metric_name,
        metric_unit,
        metric_kind,
        attributes,
    )
