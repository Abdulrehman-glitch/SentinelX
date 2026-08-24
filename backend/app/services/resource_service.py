"""Resolving an attribute bag to the Resource it describes.

Two things make this more than a dictionary lookup.

Collision safety. The identity hash is an index accelerator, not a proof. Every
lookup fetches the candidate rows sharing a hash and compares the stored
`identifying_attributes` for exact equality before accepting one. If a hash ever
matched attributes that are genuinely different, the mismatch is detected and a
new row is allocated under the next `collision_seq` rather than the two being
silently fused. SHA-256 makes that branch unreachable in practice; the point is
that correctness does not depend on it being unreachable.

Concurrency. Two agents reporting the same host at the same instant both find
nothing and both try to insert. The unique constraint is the arbiter: the insert
is `ON CONFLICT DO NOTHING` and the loser re-reads the winner's row. That is why
this is a retry loop rather than a check-then-insert, which would raise on the
race instead of resolving it.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.resource import Resource
from app.services.telemetry_identity import (
    SENTINELX_RESOURCE_ID,
    resource_identity_hash,
    split_resource_identity,
    strip_reserved,
)

# One resource cannot need more attempts than this unless something is very
# wrong; failing loudly beats spinning.
_MAX_RESOLVE_ATTEMPTS = 5


class ResourceResolutionError(RuntimeError):
    pass


def device_resource_attributes(device: Device) -> dict[str, Any]:
    """The canonical attribute view of a Device SentinelX already manages.

    Pinned by `sentinelx.resource.id` so identity survives a hostname change:
    a laptop that gets renamed is still the same device row, and must not
    become a second resource.
    """
    attributes: dict[str, Any] = {
        SENTINELX_RESOURCE_ID: str(device.id),
        "host.name": device.hostname,
        "sentinelx.device.type": device.device_type,
    }
    if device.os_name:
        attributes["os.type"] = device.os_name
    if device.agent_version:
        attributes["sentinelx.agent.version"] = device.agent_version
    return attributes


def resolve_resource(
    db: Session,
    *,
    organization_id: uuid.UUID,
    attributes: Mapping[str, Any],
    device: Device | None = None,
    trusted: bool = False,
    seen_at: datetime | None = None,
) -> Resource:
    """Find or create the Resource these attributes describe.

    `trusted` says whether the caller may set `sentinelx.*` attributes.
    SentinelX's own adapters are; an OTLP client is not, because those
    attributes can pin an identity and therefore carry authority.
    """
    identifying, descriptive, resource_type = split_resource_identity(attributes)

    if not trusted:
        identifying = strip_reserved(identifying)
        descriptive = strip_reserved(descriptive)
        # Stripping the reserved keys can empty the identity — re-derive from
        # what is left rather than creating a resource with no identity at all.
        if not identifying:
            identifying, descriptive, resource_type = split_resource_identity(
                strip_reserved(dict(attributes))
            )

    if not identifying:
        raise ResourceResolutionError(
            "Cannot identify a resource: the payload carried no usable identifying attributes "
            "(expected one of service.name, host.id, host.name, container.id or device.id)."
        )

    identity_hash = resource_identity_hash(identifying)
    now = seen_at or datetime.now(timezone.utc)

    for _ in range(_MAX_RESOLVE_ATTEMPTS):
        existing = _find_matching(db, organization_id, identity_hash, identifying)
        if existing is not None:
            _refresh(existing, descriptive, resource_type, device, now)
            return existing

        # Not present. Allocate the next collision_seq — normally 0, and
        # non-zero only in the case the module docstring describes.
        taken = set(
            db.scalars(
                select(Resource.collision_seq).where(
                    Resource.organization_id == organization_id,
                    Resource.identity_hash == identity_hash,
                )
            )
        )
        collision_seq = next(n for n in range(len(taken) + 1) if n not in taken)

        stmt = (
            pg_insert(Resource)
            .values(
                id=uuid.uuid4(),
                organization_id=organization_id,
                resource_type=resource_type,
                identity_hash=identity_hash,
                collision_seq=collision_seq,
                identifying_attributes=dict(identifying),
                attributes=dict(descriptive),
                device_id=device.id if device is not None else None,
                display_name=_display_name(identifying, device),
                last_seen_at=now,
            )
            # The racing insert wins; we re-read it on the next pass.
            .on_conflict_do_nothing(constraint="uq_resource_org_identity")
        )
        db.execute(stmt)
        db.flush()

    raise ResourceResolutionError(
        f"Could not resolve resource {identity_hash[:12]} after {_MAX_RESOLVE_ATTEMPTS} attempts."
    )


def _find_matching(
    db: Session,
    organization_id: uuid.UUID,
    identity_hash: str,
    identifying: Mapping[str, Any],
) -> Resource | None:
    """Candidates sharing the hash, filtered by actual attribute equality."""
    candidates = db.scalars(
        select(Resource)
        .where(
            Resource.organization_id == organization_id,
            Resource.identity_hash == identity_hash,
        )
        .order_by(Resource.collision_seq)
    )
    wanted = dict(identifying)
    for candidate in candidates:
        if candidate.identifying_attributes == wanted:
            return candidate
    return None


def _refresh(
    resource: Resource,
    descriptive: Mapping[str, Any],
    resource_type: str,
    device: Device | None,
    now: datetime,
) -> None:
    """Fold in whatever changed, without touching identity.

    Descriptive attributes are merged rather than replaced: an OTLP payload
    describing only `service.version` must not erase the `os.type` a previous
    payload established.
    """
    if descriptive:
        merged = dict(resource.attributes or {})
        merged.update(descriptive)
        if merged != resource.attributes:
            resource.attributes = merged

    if resource.device_id is None and device is not None:
        resource.device_id = device.id

    if resource.resource_type != resource_type and resource.resource_type == "host":
        # Only ever become more specific. A payload that omits service.name
        # must not demote a service back to a bare host.
        resource.resource_type = resource_type

    resource.last_seen_at = now


def _display_name(identifying: Mapping[str, Any], device: Device | None) -> str | None:
    if device is not None:
        return device.display_name or device.hostname
    for key in ("service.name", "host.name", "container.id", "host.id", "device.id"):
        if key in identifying:
            return str(identifying[key])[:255]
    return None
