"""Rate limiting utilities for SentinelX.

The app uses slowapi when available. A no-op fallback is provided only so the
backend can still import in constrained local environments. Production should
install slowapi from requirements.txt.

The counters themselves are NOT held here. They live in whatever shared store
app/core/rate_limit_storage.py resolves - PostgreSQL by default, Valkey when
configured - so a limit means the same thing whether one API process is running
or four. If that store is unreachable the limiter keeps enforcing per process
and /health says so; it never starts letting everything through.
"""

import hashlib
from collections.abc import Callable
from typing import Any

from app.core.config import get_settings


def client_ip_key(request) -> str:
    """Best-effort real client IP, ignoring any client-supplied Bearer token.

    Behind a reverse proxy (Cloud Run, a load balancer) request.client.host is
    the proxy, so every caller would otherwise share one bucket.
    X-Forwarded-For is only consulted when TRUSTED_PROXY_COUNT says how many
    proxies actually sit in front of us, and we then index from the RIGHT —
    the rightmost entries are appended by infrastructure we control, whereas
    anything further left was supplied by the caller and is trivially spoofed.
    With the default of 0 the header is never read at all.
    """
    peer = request.client.host if (request is not None and request.client) else "unknown"

    hops = get_settings().trusted_proxy_count
    if hops <= 0:
        return peer

    parts = [p.strip() for p in request.headers.get("X-Forwarded-For", "").split(",") if p.strip()]
    if not parts:
        return peer
    index = len(parts) - hops
    return parts[index] if 0 <= index < len(parts) else parts[0]


try:
    from slowapi import Limiter

    def _rate_limit_key(request):
        """Per-device-token for agent traffic, per-IP otherwise.

        Safe only on endpoints where a Bearer token is REQUIRED (telemetry,
        command polling) — an unauthenticated caller cannot reach those at all.
        Endpoints reachable WITHOUT authentication (login, signup, enrolment)
        must pass key_func=client_ip_key explicitly, or an attacker could mint
        a fresh bucket per request just by varying the Authorization header and
        bypass the limit entirely.
        """
        auth_header = request.headers.get("Authorization", "") if request else ""
        if auth_header.startswith("Bearer "):
            # sha256, not the builtin hash() — Python randomizes str hashing per
            # process (PYTHONHASHSEED), so the same token would bucket
            # differently across workers/restarts. Keeps the token itself out
            # of logs while making the per-token limit stable.
            digest = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()[:16]
            return f"bearer:{digest}"
        return client_ip_key(request)

    from app.core.rate_limit_storage import get_shared_storage

    # slowapi wants a URI, but we need the resolved object anyway for the
    # health probe and the fallback - so build the storage first and hand the
    # same instance to the Limiter.
    _shared = get_shared_storage()
    limiter = Limiter(key_func=_rate_limit_key, storage_uri="memory://")
    limiter._storage = _shared.active


    def limiter_health() -> dict:
        return _shared.health()
except Exception:  # pragma: no cover - fallback for broken local installs only
    class _NoopLimiter:
        def limit(self, _limit: str, *args: Any, **kwargs: Any) -> Callable:
            def decorator(func: Callable) -> Callable:
                return func
            return decorator

    limiter = _NoopLimiter()

    def limiter_health() -> dict:
        return {
            "backend": "none",
            "shared": False,
            "status": "disabled",
            "detail": "slowapi is not installed; no rate limiting is in effect.",
        }
