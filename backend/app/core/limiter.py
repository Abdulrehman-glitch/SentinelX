"""Rate limiting utilities for SentinelX.

The app uses slowapi when available. A no-op fallback is provided only so the
backend can still import in constrained local environments. Production should
install slowapi from requirements.txt.
"""

from collections.abc import Callable
from typing import Any

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    def _rate_limit_key(request):
        auth_header = request.headers.get("Authorization", "") if request else ""
        if auth_header.startswith("Bearer "):
            # Keeps token out of logs while still making device/user limits stable.
            return f"bearer:{hash(auth_header[:32])}"
        return get_remote_address(request)

    limiter = Limiter(key_func=_rate_limit_key)
except Exception:  # pragma: no cover - fallback for broken local installs only
    class _NoopLimiter:
        def limit(self, _limit: str, *args: Any, **kwargs: Any) -> Callable:
            def decorator(func: Callable) -> Callable:
                return func
            return decorator

    limiter = _NoopLimiter()
