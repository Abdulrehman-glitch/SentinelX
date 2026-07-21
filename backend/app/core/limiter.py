"""Rate limiting utilities for SentinelX.

The app uses slowapi when available. A no-op fallback is provided only so the
backend can still import in constrained local environments. Production should
install slowapi from requirements.txt.
"""

import hashlib
from collections.abc import Callable
from typing import Any

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    def _rate_limit_key(request):
        auth_header = request.headers.get("Authorization", "") if request else ""
        if auth_header.startswith("Bearer "):
            # sha256, not the builtin hash() — Python randomizes str hashing per
            # process (PYTHONHASHSEED), so the same token would bucket
            # differently across workers/restarts. Keeps the token itself out
            # of logs while making the per-token limit stable.
            digest = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()[:16]
            return f"bearer:{digest}"
        return get_remote_address(request)

    limiter = Limiter(key_func=_rate_limit_key)
except Exception:  # pragma: no cover - fallback for broken local installs only
    class _NoopLimiter:
        def limit(self, _limit: str, *args: Any, **kwargs: Any) -> Callable:
            def decorator(func: Callable) -> Callable:
                return func
            return decorator

    limiter = _NoopLimiter()
