"""Regression test for a real bug found during Sprint 7 Phase 7 load
testing: slowapi's real _rate_limit_exceeded_handler is a synchronous
function, but main.py's rate_limit_handler incorrectly `await`ed it,
crashing every actual rate-limit trip with a 500 instead of returning 429
-- completely defeating the point of rate limiting. Fixed in main.py by
checking inspect.isawaitable() before awaiting. The rest of the suite runs
with the limiter disabled (conftest.py's autouse _no_rate_limit fixture),
so nothing else exercises this path at all.
"""

from app.main import app


def test_rate_limit_exceeded_returns_429_not_500(client):
    app.state.limiter.enabled = True
    try:
        last_status = None
        for _ in range(20):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "nonexistent-e2e-probe@example.com", "password": "wrong"},
            )
            last_status = resp.status_code
            if last_status == 429:
                break
        assert last_status == 429, f"expected the rate limit to eventually trip with 429, last got {last_status}"
        assert resp.json()  # body must be readable JSON, not a crashed response
    finally:
        app.state.limiter.enabled = False
