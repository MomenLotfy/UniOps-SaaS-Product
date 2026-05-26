from functools import lru_cache
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    def fix_database_url(cls, v):
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
    def parse_cors(cls, v):
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
    RATE_LIMIT_PER_MINUTE: int = 60


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
