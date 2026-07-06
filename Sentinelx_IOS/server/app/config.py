"""Dev-server settings. This server is a development harness for the iOS
agent — the contract reference — not the production backend. Secrets default
to obvious dev values and must be overridden via environment for anything
beyond localhost."""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    database_path: str = field(
        default_factory=lambda: os.environ.get("SENTINELX_MOBILE_DB", "sentinelx_mobile_dev.db")
    )
    jwt_secret: str = field(
        default_factory=lambda: os.environ.get(
            "SENTINELX_MOBILE_JWT_SECRET", "dev-only-secret-do-not-deploy-0123456789abcdef"
        )
    )
    access_token_ttl_seconds: int = 1800
    refresh_token_ttl_seconds: int = 14 * 24 * 3600
    register_limit_per_minute: int = 10
    login_limit_per_minute: int = 20
    telemetry_limit_per_minute: int = 120
    batch_limit_per_minute: int = 30
    ws_message_limit_per_minute: int = 1200
    rate_limit_window_seconds: int = 60
    # Telemetry replay window (Codex task C3 wires these into validation).
    max_event_age_hours: int = 24
    max_event_future_minutes: int = 5
