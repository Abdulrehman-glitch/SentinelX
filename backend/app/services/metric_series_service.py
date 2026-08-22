"""Resolving a measurement to the series it belongs to.

Same collision-safe, race-safe shape as `resource_service`, with one addition:
this is where the cardinality budget is actually spent. Looking up an existing
series is always free — a tenant with a hundred thousand established series
keeps ingesting normally. Only *creating* a new one draws on the budget, which
is what makes the limit bite exactly on the runaway-cardinality case and not on
ordinary volume.

A per-request cache matters more here than it looks. A batch of five hundred
points typically references a handful of series, so without it the same series
would be resolved five hundred times, each costing a query. With it, the batch
costs one lookup per distinct series.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.metric_series import MetricSeries
from app.models.resource import Resource
from app.services.cardinality_service import (
    Rejection,
    SeriesBudget,
    budget_exhausted_rejection,
)
from app.services.telemetry_identity import AttributeValue, series_identity_hash

_MAX_RESOLVE_ATTEMPTS = 5


class SeriesResolutionError(RuntimeError):
    pass


@dataclass
class SeriesResolver:
    """Resolves series for one ingest request, caching within it.

    Deliberately request-scoped rather than a process-wide cache: a long-lived
    cache would have to be invalidated when retention deletes a series, and
    getting that wrong means writing points against a series row that no longer
    exists. The lifetime of one request needs no invalidation at all.
    """

    db: Session
    organization_id: uuid.UUID
    budget: SeriesBudget
    source: str = "sentinelx_agent"
    _cache: dict[str, MetricSeries] = field(default_factory=dict, repr=False)
    _created: int = field(default=0, repr=False)

    @property
    def created_count(self) -> int:
        return self._created

    def resolve(
        self,
        *,
        resource: Resource,
        resource_identity: str,
        metric_name: str,
        metric_unit: str | None,
        metric_kind: str,
        attributes: Mapping[str, AttributeValue],
        seen_at: datetime | None = None,
    ) -> tuple[MetricSeries | None, Rejection | None]:
        """Find or create the series, or refuse it with a reason.

        Returns (series, None) on success and (None, rejection) when the series
        does not exist and the tenant's budget for creating one is spent.
        """
        canonical = dict(attributes)
        series_hash = series_identity_hash(
            resource_identity=resource_identity,
            metric_name=metric_name,
            metric_unit=metric_unit,
            metric_kind=metric_kind,
            attributes=canonical,
        )

        cached = self._cache.get(series_hash)
        if cached is not None:
            return cached, None

        now = seen_at or datetime.now(timezone.utc)

        for _ in range(_MAX_RESOLVE_ATTEMPTS):
            existing = self._find_matching(series_hash, canonical)
            if existing is not None:
                existing.last_seen_at = now
                self._cache[series_hash] = existing
                return existing, None

            # Creating one costs budget. Checked before inserting, so a tenant
            # over the limit performs no write at all.
            if not self.budget.try_grant():
                return None, budget_exhausted_rejection(self.budget, subject=metric_name)

            taken = set(
                self.db.scalars(
                    select(MetricSeries.collision_seq).where(
                        MetricSeries.organization_id == self.organization_id,
                        MetricSeries.series_hash == series_hash,
                    )
                )
            )
            collision_seq = next(n for n in range(len(taken) + 1) if n not in taken)

            self.db.execute(
                pg_insert(MetricSeries)
                .values(
                    id=uuid.uuid4(),
                    organization_id=self.organization_id,
                    resource_id=resource.id,
                    metric_name=metric_name,
                    metric_unit=metric_unit,
                    metric_kind=metric_kind,
                    attributes=canonical,
                    series_hash=series_hash,
                    collision_seq=collision_seq,
                    source=self.source,
                    last_seen_at=now,
                )
                .on_conflict_do_nothing(constraint="uq_metric_series_org_hash")
            )
            self.db.flush()
            self._created += 1

        raise SeriesResolutionError(
            f"Could not resolve series {series_hash[:12]} after {_MAX_RESOLVE_ATTEMPTS} attempts."
        )

    def _find_matching(
        self, series_hash: str, attributes: Mapping[str, AttributeValue]
    ) -> MetricSeries | None:
        """Hash narrows the candidates; attribute equality decides."""
        candidates = self.db.scalars(
            select(MetricSeries)
            .where(
                MetricSeries.organization_id == self.organization_id,
                MetricSeries.series_hash == series_hash,
            )
            .order_by(MetricSeries.collision_seq)
        )
        wanted = dict(attributes)
        for candidate in candidates:
            if candidate.attributes == wanted:
                return candidate
        return None
