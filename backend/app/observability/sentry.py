"""
Sprint 3 R29 — Sentry integration.

`init_sentry()` reads ``SENTRY_DSN`` from settings and initialises the
sentry-sdk with the project's safety guard-rails:

  - ``send_default_pii=False``         never send IP, headers, etc.
  - ``attach_stacktrace=True``          full stack on every event.
  - ``traces_sample_rate`` from env (default ``0.1`` in production).
  - ``profiles_sample_rate`` from env (default ``0.0`` — opt-in).
  - ``environment`` from settings.APP_ENV.
  - ``release`` from settings.APP_VERSION.
  - Celery auto-integration when Celery is installed.

`capture_exception_safe()` is the helper the global exception handler
uses — it never raises, even if Sentry is unreachable.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


_INITIALISED = False


def init_sentry(
    *,
    dsn: str = "",
    environment: str = "",
    release: str = "",
    traces_sample_rate: float | None = None,
    profiles_sample_rate: float | None = None,
) -> bool:
    """
    Initialise the Sentry SDK.  Idempotent.

    Returns ``True`` when DSN was provided and Sentry accepted the
    configuration; ``False`` when DSN is empty or import failed.
    """
    global _INITIALISED
    if _INITIALISED:
        return True

    dsn = (dsn or os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        logger.info("Sentry DSN not configured — error capture is local-only")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        logger.info("sentry-sdk not installed — error capture is local-only")
        return False

    env = environment or os.getenv("APP_ENV", "development")
    release = release or os.getenv("APP_VERSION", "1.0.0")
    sample_rate = (
        traces_sample_rate
        if traces_sample_rate is not None
        else float(
            os.getenv(
                "SENTRY_TRACES_SAMPLE_RATE", "0.1" if env in {"production", "prod"} else "0.0"
            )
        )
    )
    profile_rate = (
        profiles_sample_rate
        if profiles_sample_rate is not None
        else float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.0"))
    )

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=env,
            release=release,
            send_default_pii=False,
            attach_stacktrace=True,
            traces_sample_rate=sample_rate,
            profiles_sample_rate=profile_rate,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
                CeleryIntegration(),
            ],
            before_send=_before_send,  # type: ignore[arg-type]
            before_send_transaction=_before_send_transaction,  # type: ignore[arg-type]
        )
        _INITIALISED = True
        logger.info("Sentry initialised (env=%s release=%s)", env, release)
        return True
    except Exception:
        logger.exception("Sentry init failed")
        return False


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Strip PII / sensitive fields before transmission."""
    try:
        request = event.get("request") or {}
        headers = request.get("headers") or {}
        for k in ("authorization", "cookie", "x-api-key", "x-secret-key"):
            if k in headers:
                headers[k] = "[REDACTED]"
        if "data" in event:
            event["data"] = _redact_payload(event["data"])
        if "extra" in event:
            event["extra"] = _redact_payload(event["extra"])
    except Exception:  # pragma: no cover - non-fatal
        pass
    return event


def _before_send_transaction(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Attach correlation_id / tenant_id tags to every transaction."""
    try:
        from . import context as _ctx

        ctx = _ctx.current_context()
        tags = event.setdefault("tags", {})
        if ctx.get("correlation_id"):
            tags.setdefault("correlation_id", ctx["correlation_id"])
        if ctx.get("tenant_id"):
            tags.setdefault("tenant_id", ctx["tenant_id"])
    except Exception:  # pragma: no cover - non-fatal
        pass
    return event


def _redact_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    redacted = {}
    for k, v in payload.items():
        lk = str(k).lower()
        if any(
            s in lk for s in ("password", "secret", "token", "apikey", "api_key", "authorization")
        ):
            redacted[k] = "[REDACTED]"
        else:
            redacted[k] = v
    return redacted


def capture_exception_safe(exc: BaseException) -> None:
    """Capture ``exc`` without ever raising."""
    if not _INITIALISED:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:  # pragma: no cover - non-fatal
        logger.exception("sentry capture_exception failed")


def capture_message_safe(message: str, *, level: str = "info") -> None:
    """Capture ``message`` without ever raising."""
    if not _INITIALISED:
        return
    try:
        import sentry_sdk

        # sentry_sdk.capture_message is overloaded; level must be one of
        # the literal "fatal|critical|error|warning|info|debug".
        sentry_sdk.capture_message(message, level=level)  # type: ignore[arg-type]
    except Exception:  # pragma: no cover - non-fatal
        logger.exception("sentry capture_message failed")


__all__ = ["init_sentry", "capture_exception_safe", "capture_message_safe"] + ["_INITIALISED"]
