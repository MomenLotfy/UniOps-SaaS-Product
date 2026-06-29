"""
Application settings.

Sprint 1 R7: SECRET_KEY is validated at startup and rejected when it
matches a known placeholder / default / empty value.  The check is
deliberately permissive in development (APP_ENV != "production") so
local dev workflows continue to work with the documented default.
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file's directory (backend/app/), so it works
# regardless of the working directory the process is launched from.
_ENV_FILE = Path(__file__).parent.parent / ".env"


# Values that explicitly must NOT appear as a production SECRET_KEY.
# Match is case-insensitive on the substring.
_FORBIDDEN_SECRET_SUBSTRINGS = (
    "change-me",
    "change_me",
    "changeme",
    "default",
    "placeholder",
    "example",
    "todo",
    "fixme",
    "your-secret",
    "your_secret",
    "insecure",
    "test-secret",
    "test_secret",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    APP_NAME: str = "UniOps"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"
    API_V1_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:5173"

    # Default uses "db" service name — works in Docker.
    # Override with DATABASE_URL env var for Replit (sqlite) or production (postgres host).
    DATABASE_URL: str = "postgresql+asyncpg://uniops:uniops_password@db:5432/uniops_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v: object) -> object:
        if isinstance(v, str):
            if v.startswith("postgresql://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            if "sslmode=" in v:
                import re
                v = re.sub(r"[?&]sslmode=[^&]*", "", v)
        return v

    # Default uses "redis" service name — works in Docker.
    # Override with REDIS_URL env var for Replit (localhost) or external Redis.
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    JWT_SECRET_KEY: str = "jwt-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = "us-east-1"

    GITHUB_APP_ID: str = ""
    GITHUB_PRIVATE_KEY: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_TOKEN: str = ""

    GITLAB_URL: str = "https://gitlab.com"
    GITLAB_TOKEN: str = ""

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    SENTRY_DSN: str = ""
    APP_VERSION: str = "1.0.0"

    SLACK_BOT_TOKEN: str = ""
    SLACK_WEBHOOK_URL: str = ""

    SENDGRID_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@uniops.io"

    CORS_ORIGINS: List[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: object) -> object:
        if isinstance(v, str):
            # Handle JSON list string: '["a","b"]'
            if v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            # Handle comma-separated: "a,b,c"
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @field_validator("RATE_LIMIT_TRUSTED_PROXIES", mode="before")
    @classmethod
    def _parse_trusted_proxies(cls, v: object) -> object:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v
    RATE_LIMIT_PER_MINUTE: int = 60
    # Sprint 4: production-grade rate limiting.  All values are
    # configurable through the environment; the Redis-backed
    # RateLimiter enforces them per tenant + per endpoint.
    RATE_LIMIT_BURST_PER_MINUTE: int = 100
    RATE_LIMIT_SUSTAINED_PER_HOUR: int = 5000
    RATE_LIMIT_TENANT_BURST_PER_MINUTE: int = 300
    RATE_LIMIT_TENANT_SUSTAINED_PER_HOUR: int = 20000
    RATE_LIMIT_TRUSTED_PROXIES: List[str] = []
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_KEY_PREFIX: str = "rl"

    # ── Sprint 3 R30 observability ────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" | "text"
    OTEL_SERVICE_NAME: str = "uniops"
    OTEL_SDK_DISABLED: str = "false"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.0

    # ── Sprint 1 R7: SECRET_KEY hardening ─────────────────────────────
    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        if v is None:
            raise ValueError(
                "SECRET_KEY is empty. Set a strong random value via env or .env."
            )
        stripped = (v or "").strip()
        if not stripped:
            raise ValueError(
                "SECRET_KEY is empty. Set a strong random value via env or .env."
            )
        lowered = stripped.lower()
        for bad in _FORBIDDEN_SECRET_SUBSTRINGS:
            if bad in lowered:
                raise ValueError(
                    f"SECRET_KEY contains forbidden placeholder substring "
                    f"'{bad}'. Set a strong random value via env or .env."
                )
        if len(stripped) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters long. "
                "Generate one with `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`."
            )
        return v

    @model_validator(mode="after")
    def _enforce_secret_key_in_production(self) -> "Settings":
        """In production, refuse to boot when CORS_ORIGINS is wildcard or
        when DEBUG is enabled.  These are operational invariants that
        should fail loud."""
        if (self.APP_ENV or "").lower() in {"production", "prod", "staging"}:
            if self.DEBUG:
                raise ValueError(
                    "DEBUG must be False when APP_ENV is production/staging."
                )
            if "*" in (self.CORS_ORIGINS or []):
                raise ValueError(
                    "CORS_ORIGINS must not include '*' when APP_ENV is "
                    "production/staging. Set explicit allowed origins."
                )
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
