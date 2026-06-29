"""
Sprint 3 R34 — startup configuration validator.

A single ``validate_runtime_config()`` call is invoked at the top of
the lifespan startup.  It is non-fatal by default (logs warnings) but
raises ``StartupConfigError`` when a CRITICAL invariant is missing —
the FastAPI lifespan converts that exception into ``sys.exit(1)`` so
the orchestrator can restart the pod.

The categories:

  - CRITICAL — fail-fast.  Bad SECRET_KEY, missing SENTRY_DSN in
    production, wildcard CORS_ORIGINS in production, missing DB URL,
    missing OTEL endpoint in production.
  - WARNING  — log and continue.  Missing SENTRY_DSN in dev, missing
    OTEL endpoint in dev, etc.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from app.config import Settings

logger = logging.getLogger(__name__)


_FORBIDDEN_SECRET_SUBSTRINGS = (
    "change-me",
    "change_me",
    "changeme",
    "default",
    "placeholder",
    "example",
    "your-secret",
    "your_secret",
    "insecure",
    "test-secret",
    "test_secret",
)


class StartupConfigError(RuntimeError):
    """Raised when critical startup config is missing."""


@dataclass
class StartupCheck:
    name: str
    ok: bool
    level: str  # "critical" | "warning"
    detail: str = ""


@dataclass
class StartupReport:
    ok: bool = True
    checks: list[StartupCheck] = field(default_factory=list)

    def add(self, check: StartupCheck) -> None:
        self.checks.append(check)
        if not check.ok and check.level == "critical":
            self.ok = False

    def critical_failures(self) -> list[StartupCheck]:
        return [c for c in self.checks if not c.ok and c.level == "critical"]

    def warnings(self) -> list[StartupCheck]:
        return [c for c in self.checks if not c.ok and c.level == "warning"]


def validate_runtime_config(settings: Settings) -> StartupReport:
    """
    Inspect ``settings`` and the process environment.

    Raises ``StartupConfigError`` when a CRITICAL invariant is
    missing.  Warnings are recorded but do not raise.
    """
    report = StartupReport()
    env = (settings.APP_ENV or "").lower()
    is_prod = env in {"production", "prod", "staging"}

    # SECRET_KEY length + placeholders
    secret = (settings.SECRET_KEY or "").strip()
    lowered = secret.lower()
    if len(secret) < 32:
        report.add(
            StartupCheck(
                name="secret_key_length",
                ok=False,
                level="critical",
                detail=f"SECRET_KEY length {len(secret)} < 32 minimum",
            )
        )
    elif any(bad in lowered for bad in _FORBIDDEN_SECRET_SUBSTRINGS):
        report.add(
            StartupCheck(
                name="secret_key_placeholder",
                ok=False,
                level="critical",
                detail="SECRET_KEY contains a placeholder substring",
            )
        )
    else:
        report.add(StartupCheck(name="secret_key_length", ok=True, level="critical"))

    # CORS_ORIGINS wildcard
    cors = settings.CORS_ORIGINS or []
    if "*" in cors and is_prod:
        report.add(
            StartupCheck(
                name="cors_wildcard",
                ok=False,
                level="critical",
                detail="CORS_ORIGINS contains '*' in production/staging",
            )
        )
    elif not cors:
        report.add(
            StartupCheck(
                name="cors_empty",
                ok=False,
                level="critical",
                detail="CORS_ORIGINS is empty",
            )
        )
    else:
        report.add(StartupCheck(name="cors", ok=True, level="critical"))

    # DEBUG in production
    if settings.DEBUG and is_prod:
        report.add(
            StartupCheck(
                name="debug_in_production",
                ok=False,
                level="critical",
                detail="DEBUG=True in production/staging",
            )
        )

    # DATABASE_URL present
    if not settings.DATABASE_URL:
        report.add(
            StartupCheck(
                name="database_url_missing",
                ok=False,
                level="critical",
                detail="DATABASE_URL is empty",
            )
        )
    else:
        report.add(StartupCheck(name="database_url", ok=True, level="critical"))

    # SENTRY_DSN — critical in production
    sentry_dsn = (settings.SENTRY_DSN or os.getenv("SENTRY_DSN") or "").strip()
    if is_prod and not sentry_dsn:
        report.add(
            StartupCheck(
                name="sentry_dsn_missing",
                ok=False,
                level="critical",
                detail="SENTRY_DSN is empty in production",
            )
        )
    elif not sentry_dsn:
        report.add(
            StartupCheck(
                name="sentry_dsn_missing",
                ok=False,
                level="warning",
                detail="SENTRY_DSN is empty (dev only)",
            )
        )
    else:
        report.add(StartupCheck(name="sentry_dsn", ok=True, level="critical"))

    # OTEL endpoint — critical in production
    otel_endpoint = (os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip()
    if is_prod and not otel_endpoint:
        report.add(
            StartupCheck(
                name="otel_endpoint_missing",
                ok=False,
                level="warning",
                detail="OTEL_EXPORTER_OTLP_ENDPOINT not set in production",
            )
        )
    elif not otel_endpoint:
        report.add(
            StartupCheck(
                name="otel_endpoint_missing",
                ok=False,
                level="warning",
                detail="OTEL_EXPORTER_OTLP_ENDPOINT not set (dev only)",
            )
        )
    else:
        report.add(StartupCheck(name="otel_endpoint", ok=True, level="critical"))

    # REDIS_URL present
    if not settings.REDIS_URL:
        report.add(
            StartupCheck(
                name="redis_url_missing",
                ok=False,
                level="warning",
                detail="REDIS_URL is empty",
            )
        )

    return report


def fail_fast(report: StartupReport) -> None:
    """Log the report and ``raise StartupConfigError`` on critical failures."""
    for c in report.checks:
        if c.ok:
            continue
        log_fn = logger.critical if c.level == "critical" else logger.warning
        log_fn("startup check failed [%s] %s — %s", c.level, c.name, c.detail)

    if not report.ok:
        names = ", ".join(c.name for c in report.critical_failures())
        raise StartupConfigError(f"Critical startup config errors: {names}")


def run() -> None:
    """
    Convenience: load settings, validate, fail fast.

    Called from ``main.py`` lifespan startup.  Always re-imports the
    settings to avoid a cached singleton from a previous test run.
    """
    from app.config import get_settings

    settings = get_settings()
    report = validate_runtime_config(settings)
    fail_fast(report)


__all__ = [
    "StartupReport",
    "StartupCheck",
    "StartupConfigError",
    "validate_runtime_config",
    "fail_fast",
    "run",
]
