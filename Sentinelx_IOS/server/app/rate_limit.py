"""In-memory fixed-window rate limiter for the mobile dev server."""

from __future__ import annotations

from dataclasses import dataclass
import math
import time

from fastapi import Request

from .errors import APIError


@dataclass
class Bucket:
    reset_at: float
    count: int = 0


class RateLimiter:
    def __init__(self, window_seconds: int = 60) -> None:
        self.window_seconds = max(1, window_seconds)
        self._buckets: dict[str, Bucket] = {}

    def check(self, scope: str, key: str, limit: int) -> int | None:
        if limit <= 0:
            return None

        now = time.monotonic()
        bucket_key = f"{scope}:{key}"
        bucket = self._buckets.get(bucket_key)
        if bucket is None or now >= bucket.reset_at:
            self._buckets[bucket_key] = Bucket(reset_at=now + self.window_seconds, count=1)
            return None

        if bucket.count >= limit:
            return max(1, math.ceil(bucket.reset_at - now))

        bucket.count += 1
        return None


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, scope: str, key: str, limit: int, message: str) -> None:
    retry_after = request.app.state.rate_limiter.check(scope, key, limit)
    if retry_after is not None:
        raise APIError(
            429,
            "RATE_LIMITED",
            message,
            {"retry_after_seconds": retry_after},
        )
