"""
Sprint 3 R30 — structlog configuration.

`configure_structlog()` is the single entry point for wiring structlog
into the project.  It is idempotent: calling it twice is a no-op (the
underlying ``configure`` raises if already configured, so we guard with
a module-level flag).

Behaviour:

  - ``LOG_FORMAT=json`` (default in production) → JSON renderer with
    context fields.
  - ``LOG_FORMAT=text`` (default in development) → pretty console
    renderer with colors via the dev console (loguru-equivalent).
  - ``LOG_LEVEL`` controls the root level (default ``INFO``).

Both renderers pull the live context from ``app.observability.context``
so every line carries trace_id / correlation_id / request_id /
tenant_id / user_id without callers passing them explicitly.

This module never imports loguru.  The legacy ``app/utils/logger.py``
imports from here when ``LOG_FORMAT=json`` is set, so the two can
coexist during the migration.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import sys
from typing import Any

from . import context as _ctx
from .formatters import render_json

_CONFIGURED = False


def _level_from_env() -> int:
    name = (os.getenv("LOG_LEVEL") or "INFO").upper()
    return getattr(logging, name, logging.INFO)


def _add_context(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Inject the current observability context into every log event."""
    ctx = _ctx.current_context()
    for k, v in ctx.items():
        if v is not None:
            event_dict.setdefault(k, v)
    return event_dict


def _json_renderer(_: Any, __: str, event_dict: dict[str, Any]) -> str:
    """structlog processor: format the final event dict as JSON."""
    return render_json(
        level=event_dict.get("level", "info"),
        event=event_dict.get("event", ""),
        timestamp=event_dict.get("timestamp") or _now(),
        module=event_dict.get("module", ""),
        service=event_dict.get("service", os.getenv("APP_NAME", "uniops")),
        environment=event_dict.get("environment", os.getenv("APP_ENV", "development")),
        version=event_dict.get("version", os.getenv("APP_VERSION", "1.0.0")),
        extra=_strip_reserved(event_dict),
    )


def _strip_reserved(d: dict[str, Any]) -> dict[str, Any]:
    reserved = {"level", "event", "timestamp", "module", "service", "environment", "version"}
    return {k: v for k, v in d.items() if k not in reserved}


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.UTC)


def configure_structlog(*, force: bool = False) -> bool:
    """
    Wire structlog into the standard logging module.

    Returns ``True`` if the call actually applied configuration, ``False``
    when skipped (already configured).  ``force=True`` reconfigures
    even if previously applied — useful in tests.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return False

    fmt = (os.getenv("LOG_FORMAT") or "json").lower()
    level = _level_from_env()

    try:
        import structlog

        shared_processors: list[Any] = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_context,
        ]
        if fmt == "json":
            renderer: Any = structlog.processors.JSONRenderer(serializer=_json_renderer)
        else:
            renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                renderer,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        _CONFIGURED = True
        return True
    except ImportError:
        # structlog not installed — keep loguru default.
        return False
    except Exception:
        # Any other configuration error — log and fall back to loguru.
        logging.getLogger(__name__).exception("configure_structlog failed")
        return False


def get_logger(name: str) -> Any:
    """Return a structlog logger bound to ``name``.  Falls back to stdlib."""
    try:
        import structlog

        return structlog.get_logger(name)
    except ImportError:
        return logging.getLogger(name)


__all__ = ["configure_structlog", "get_logger"]
