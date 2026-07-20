from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """
    Central application configuration loaded from environment variables / backend/.env.
    """

    app_name: str = "SentinelX API"
    app_env: str = "development"
    app_version: str = "2.0.0"

    database_url: str

    backend_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    jwt_secret_key: str = "change-this-dev-secret-before-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Rate limiting (requests per window) — used by route decorators via get_settings()
    rate_limit_login: str = "15/minute"
    rate_limit_signup: str = "5/minute"
    rate_limit_api: str = "300/minute"
    rate_limit_telemetry: str = "120/minute"
    rate_limit_enroll: str = "10/minute"

    # Security headers (disable in dev if needed)
    security_headers_enabled: bool = True

    # AI observability shadow-mode kill switch — flip to False to disable
    # POST /observability/pipeline/run without a code rollback.
    observability_shadow_mode_enabled: bool = True

    # Safe Recovery Orchestration (Sprint 3) kill switch — flip to False to
    # disable /recovery-commands and /agent/commands endpoints without a
    # code rollback. Path is resolved relative to backend/ if not absolute.
    recovery_orchestration_enabled: bool = True
    recovery_signing_private_key_path: str = ".secrets/recovery_signing_key.pem"
    recovery_command_default_ttl_seconds: int = 300

    # Hybrid detection engine (Sprint 4-6) kill switch — flip to False to
    # disable /hybrid/decisions/run without a code rollback.
    hybrid_detection_enabled: bool = True

    # Historical replay (Sprint 4-6) kill switch — independent of the flag
    # above since replay has its own safety property (read-only, never
    # creates alerts/incidents/recovery commands).
    historical_replay_enabled: bool = True

    # Verified low-risk self-healing (Sprint 4-6, Stage 4) — when True, the
    # hybrid pipeline automatically proposes an AI recovery recommendation
    # after scoring each window (still gated by the deterministic policy
    # engine/capability/cooldown/circuit-breaker checks below it). Defaults
    # to False until validated in shadow — flip to True to enable, or back
    # to False to instantly stop new automatic proposals without a code
    # rollback. The explicit POST /hybrid/decisions/{id}/propose-recovery
    # endpoint always works regardless of this flag, for human-triggered use.
    self_healing_automation_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
