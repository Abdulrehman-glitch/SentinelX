"""Sprint 7 Phase 4: boot-time guard against the default JWT secret.

Settings() must refuse to construct (i.e. the app must refuse to boot) when
APP_ENV=production still has the placeholder JWT_SECRET_KEY, since that
placeholder is public (it's in this repo).
"""

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_JWT_SECRET_PLACEHOLDER, Settings

_DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/db"


def test_production_boot_refuses_default_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(
            database_url=_DATABASE_URL,
            app_env="production",
            jwt_secret_key=DEFAULT_JWT_SECRET_PLACEHOLDER,
        )


def test_production_boot_accepts_a_real_jwt_secret():
    settings = Settings(
        database_url=_DATABASE_URL,
        app_env="production",
        jwt_secret_key="a-real-randomly-generated-secret",
    )
    assert settings.jwt_secret_key == "a-real-randomly-generated-secret"


def test_development_boot_allows_the_default_jwt_secret():
    settings = Settings(
        database_url=_DATABASE_URL,
        app_env="development",
        jwt_secret_key=DEFAULT_JWT_SECRET_PLACEHOLDER,
    )
    assert settings.jwt_secret_key == DEFAULT_JWT_SECRET_PLACEHOLDER
