import os
import subprocess
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET_PLACEHOLDER = "change-this-dev-secret-before-production"


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


def _detect_commit_sha() -> str:
    """Resolve the running commit SHA for /health diagnostics.

    Deploys should set SENTINELX_COMMIT_SHA explicitly (the deployed
    artifact usually has no .git directory); falls back to a local git
    lookup for dev, then "unknown".
    """
    env_sha = os.getenv("SENTINELX_COMMIT_SHA", "").strip()
    if env_sha:
        return env_sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


class Settings(BaseSettings):
    """
    Central application configuration loaded from environment variables / backend/.env.
    """

    app_name: str = "SentinelX API"
    app_env: str = "development"
    app_version: str = "3.1.0"
    commit_sha: str = Field(default_factory=_detect_commit_sha)

    database_url: str

    backend_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    jwt_secret_key: str = DEFAULT_JWT_SECRET_PLACEHOLDER
    jwt_algorithm: str = "HS256"

    # Access tokens are now short-lived and paired with a server-side session
    # (see models/user_session.py). 15 minutes bounds the damage from a leaked
    # access token; the browser stays signed in via silent refresh, so the
    # user never sees the difference. The old 1440-minute default only made
    # sense because there was nothing to refresh with.
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14

    # Bound how long a single sign-in can be kept alive by rotation. Without
    # this, a refresh family that is used regularly never ends.
    session_absolute_max_days: int = 30

    # Validated on every decode. `aud`/`iss` stop a token minted for some
    # other service that happens to share the secret from being accepted here.
    jwt_issuer: str = "sentinelx"
    jwt_audience: str = "sentinelx-api"

    # ── Browser session cookies ──────────────────────────────────────────
    # The refresh token lives in an HttpOnly cookie so JavaScript (and thus
    # any XSS payload) cannot read it. The CSRF cookie is deliberately NOT
    # HttpOnly: the double-submit pattern needs the SPA to read it back.
    session_cookie_name: str = "sx_refresh"
    csrf_cookie_name: str = "sx_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    # Path-scoped so the refresh cookie is only ever sent to the endpoints
    # that consume it, rather than riding along on every API call.
    session_cookie_path: str = "/api/v1/auth"
    session_cookie_domain: str | None = None

    # "lax" is correct when the dashboard and API share a registrable domain
    # (including localhost:5173 -> localhost:8000 in dev). A split-origin
    # deployment needs "none", which browsers only honour together with
    # Secure — enforced by the validator below.
    session_cookie_samesite: str = "lax"

    # None means "decide from app_env": secure in production, plain in dev so
    # http://localhost works. Set explicitly to override.
    session_cookie_secure: bool | None = None

    # Rate limiting (requests per window) — used by route decorators via get_settings()
    rate_limit_login: str = "15/minute"
    rate_limit_signup: str = "5/minute"
    rate_limit_api: str = "300/minute"
    rate_limit_telemetry: str = "120/minute"
    rate_limit_enroll: str = "10/minute"

    # Security headers (disable in dev if needed)
    security_headers_enabled: bool = True

    # Open public self-registration via POST /auth/signup. Left on for local
    # work, but forced off in production unless PUBLIC_SIGNUP_ENABLED is set
    # explicitly (see the validator below) — on a public deployment anyone
    # could otherwise create an account, and the very first one becomes admin.
    # Bootstrap the first production admin with `python -m app.db.create_admin`.
    public_signup_enabled: bool = True

    # How many reverse proxies sit in front of the app. 0 (default) means the
    # app is directly exposed and X-Forwarded-For is ignored entirely, since a
    # client can forge it. Set to 1 behind Cloud Run / a single load balancer
    # so per-IP rate limiting and security-log attribution see the real caller
    # rather than bucketing the whole internet under the proxy's address.
    trusted_proxy_count: int = 0

    # Pre-v2 opaque device tokens. Resolving one costs an argon2 verification
    # against EVERY active credential, so an unauthenticated caller can burn
    # O(fleet size) CPU per request. No token-minting path has produced this
    # format since Sprint 1, so it stays off unless a legacy fleet needs it.
    allow_legacy_device_tokens: bool = False

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

    @model_validator(mode="after")
    def _forbid_default_jwt_secret_in_production(self) -> "Settings":
        if self.app_env == "production" and self.jwt_secret_key == DEFAULT_JWT_SECRET_PLACEHOLDER:
            raise ValueError(
                "Refusing to start with APP_ENV=production and the default JWT_SECRET_KEY "
                "placeholder. Set a real secret (e.g. `python -c \"import secrets; "
                "print(secrets.token_urlsafe(64))\"`) in the production environment config."
            )
        return self

    @model_validator(mode="after")
    def _close_public_signup_in_production(self) -> "Settings":
        # Secure by default: production turns open registration off unless the
        # operator opted in explicitly. model_fields_set tells us whether the
        # value actually came from the environment/.env or is just the default,
        # so an explicit PUBLIC_SIGNUP_ENABLED=true is still honoured.
        if self.app_env == "production" and "public_signup_enabled" not in self.model_fields_set:
            self.public_signup_enabled = False
        return self

    @model_validator(mode="after")
    def _resolve_and_validate_cookie_security(self) -> "Settings":
        # Secure defaults to on in production and off elsewhere, so a
        # developer on http://localhost never has to weaken a production
        # setting to get a working login.
        if self.session_cookie_secure is None:
            self.session_cookie_secure = self.app_env == "production"

        samesite = self.session_cookie_samesite.lower()
        if samesite not in {"lax", "strict", "none"}:
            raise ValueError(
                f"SESSION_COOKIE_SAMESITE must be one of lax/strict/none, got '{self.session_cookie_samesite}'."
            )
        self.session_cookie_samesite = samesite

        # Browsers silently drop SameSite=None cookies that are not Secure,
        # which would present as "login works, refresh always 401" — fail
        # loudly at startup instead.
        if samesite == "none" and not self.session_cookie_secure:
            raise ValueError(
                "SESSION_COOKIE_SAMESITE=none requires SESSION_COOKIE_SECURE=true; browsers reject "
                "SameSite=None cookies sent without the Secure attribute."
            )

        if self.app_env == "production" and not self.session_cookie_secure:
            raise ValueError(
                "Refusing to start with APP_ENV=production and SESSION_COOKIE_SECURE=false — the refresh "
                "cookie would be transmitted over plaintext HTTP."
            )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
