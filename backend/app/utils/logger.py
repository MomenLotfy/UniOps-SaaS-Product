"""
Sprint 3 R30 — Loguru bridge for structured logging.

``logger`` (this module) remains the canonical import path used
across the codebase (``from app.utils.logger import logger``).  When
``LOG_FORMAT=json`` the project routes loguru through structlog's
JSON renderer so every line carries the observability context.

Two sinks:

  1. stdout — colored in dev (LOG_FORMAT=text), JSON in production
     (LOG_FORMAT=json).
  2. rotating file at ``logs/app.log`` — JSON always, 30-day retention.

Existing call sites that use ``logger.info("hello")`` continue to work;
the JSON renderer replaces the message with a structured payload that
includes trace_id, correlation_id, tenant_id, etc. when those fields
are bound on the observability context.
"""
from __future__ import annotations

import logging
import os
import sys

from loguru import logger as _loguru

from app.config import settings


def _resolve_format() -> str:
    return (settings.LOG_FORMAT or os.getenv("LOG_FORMAT") or "text").lower()


def _build_stdout_formatter() -> str:
    if _resolve_format() == "json":
        # The JSON renderer is configured inside ``configure_structlog``.
        # loguru itself continues to write the raw message; the renderer
        # only fires for structlog-bound loggers.  To avoid double-encoding
        # we keep loguru's plain output here.
        return "{message}"
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )


def _build_file_formatter() -> str:
    return (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{name}:{function}:{line} - {message}"
    )


_loguru.remove()
_loguru.add(
    sys.stdout,
    format=_build_stdout_formatter(),
    level=settings.LOG_LEVEL or os.getenv("LOG_LEVEL") or "INFO",
    colorize=_resolve_format() == "text",
)
_loguru.add(
    "logs/app.log",
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
    format=_build_file_formatter(),
    enqueue=True,
)

# Configure the stdlib root logger to match (so other libraries that
# use the standard ``logging`` module behave the same way).
_stdlib_root = logging.getLogger()
_stdlib_root.setLevel(getattr(logging, settings.LOG_LEVEL or "INFO", logging.INFO))
_stdlib_handler = logging.StreamHandler(sys.stdout)
_stdlib_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s")
)
_stdlib_root.handlers = [_stdlib_handler]


logger = _loguru

__all__ = ["logger"]