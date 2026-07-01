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

    # Security headers (disable in dev if needed)
    security_headers_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
