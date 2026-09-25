"""Application settings, loaded from environment variables.

This is the ONLY place the app reads configuration. Everything else asks for a
`Settings` object instead of calling `os.environ` directly, which gives us:

- validation at startup (a missing/malformed DATABASE_URL fails immediately
  with a clear error, not later on the first request), and
- one place to see every knob the app has.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo-root `.env` (one level above /backend). We compute an absolute path
# so it works no matter which directory you launch the app or tests from.
_REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # Real environment variables always win over values in the .env file, so
    # CI and production (which have no .env) just set env vars.
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        # The shared .env also holds POSTGRES_* vars meant for Docker; ignore
        # anything we don't declare rather than erroring on it.
        extra="ignore",
    )

    # No default on purpose: if it's missing we want a loud startup failure,
    # not a silent connection to some unexpected database.
    database_url: str
    environment: Literal["local", "test", "production"] = "local"

    # Signs and verifies access tokens (HS256). Anyone holding it can mint a
    # token for any user, so it's a secret: env var only, never committed.
    # 32+ chars because a short HMAC key can be brute-forced offline from a
    # single captured token.
    jwt_secret: str = Field(min_length=32)
    # Short-lived by design: a stolen token stops working within the hour.
    access_token_ttl_minutes: int = Field(default=60, gt=0, le=24 * 60)


@lru_cache
def get_settings() -> Settings:
    """Return the settings, built once and cached.

    Used as a FastAPI dependency, so tests can swap it out with
    `app.dependency_overrides[get_settings] = ...` if they need to.
    """
    # Required fields are filled from the environment; the pydantic mypy
    # plugin (enabled in pyproject.toml) knows this, so no type: ignore needed.
    return Settings()
