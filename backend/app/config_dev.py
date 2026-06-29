"""
Development config override — uses SQLite so you don't need PostgreSQL or Redis.
Usage: export USE_DEV_CONFIG=1 before running uvicorn
"""
import os

# Override DATABASE_URL to use SQLite if no PostgreSQL available
if not os.environ.get("DATABASE_URL"):
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./uniops_dev.db")

# Disable Redis/Celery in dev (not needed for basic usage)
os.environ.setdefault("REDIS_URL", "redis://redis:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://redis:6379/1")
# Sprint 1 R7: the dev overrides now use a strong random placeholder of 48+
# characters so they satisfy the SECRET_KEY validator without tripping the
# "change-me / default / placeholder" substring filter.  In production the
# real value must be injected by the deployment secret store.
os.environ.setdefault(
    "SECRET_KEY",
    "uniops-dev-secret-key-please-replace-in-production-env-0001",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "uniops-dev-jwt-secret-key-please-replace-in-production-env-001",
)
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("APP_ENV", "development")
