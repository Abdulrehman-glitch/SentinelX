from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application configuration.

    Values are loaded from environment variables or the local .env file.
    This prevents secrets such as database passwords being hard-coded in
    the source code.
    """

    app_name: str = "SentinelX API"
    app_env: str = "development"
    app_version: str = "0.1.0"

    database_url: str

    backend_cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """
    Cache settings so they are not repeatedly reloaded on every request.
    """
    return Settings()