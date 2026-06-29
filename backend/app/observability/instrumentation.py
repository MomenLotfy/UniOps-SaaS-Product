"""
Sprint 3 R28 — OpenTelemetry auto-instrumentation.

Each ``instrument_*`` helper is tolerant: missing packages degrade
to a log line and the rest of the system keeps running.

The instrumentations we wire:

  - FastAPI (HTTP request spans)
  - SQLAlchemy (DB query spans)
  - asyncpg (low-level DB protocol spans)
  - Redis (cache spans)
  - Celery (task spans)
  - Logging (correlate ``logger.info(...)`` lines with active span)

Wiring is one-shot: ``instrument_app(app)`` may be called twice
without effect (we guard with a module-level flag).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_INSTRUMENTED = {
    "fastapi": False,
    "sqlalchemy": False,
    "asyncpg": False,
    "redis": False,
    "celery": False,
    "logging": False,
}


def instrument_app(app: Any) -> bool:
    """Instrument a FastAPI app for HTTP request spans."""
    if _INSTRUMENTED["fastapi"]:
        return True
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        _INSTRUMENTED["fastapi"] = True
        return True
    except ImportError:
        logger.info("opentelemetry-instrumentation-fastapi not installed")
        return False
    except Exception:
        logger.exception("FastAPI instrumentation failed")
        return False


def instrument_sqlalchemy(engine: Any) -> bool:
    if _INSTRUMENTED["sqlalchemy"]:
        return True
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=engine)
        _INSTRUMENTED["sqlalchemy"] = True
        return True
    except ImportError:
        return False
    except Exception:
        logger.exception("SQLAlchemy instrumentation failed")
        return False


def instrument_asyncpg() -> bool:
    if _INSTRUMENTED["asyncpg"]:
        return True
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()
        _INSTRUMENTED["asyncpg"] = True
        return True
    except ImportError:
        return False
    except Exception:
        logger.exception("asyncpg instrumentation failed")
        return False


def instrument_redis() -> bool:
    if _INSTRUMENTED["redis"]:
        return True
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
        _INSTRUMENTED["redis"] = True
        return True
    except ImportError:
        return False
    except Exception:
        logger.exception("Redis instrumentation failed")
        return False


def instrument_celery(app: Any) -> bool:
    if _INSTRUMENTED["celery"]:
        return True
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()
        _INSTRUMENTED["celery"] = True
        return True
    except ImportError:
        return False
    except Exception:
        logger.exception("Celery instrumentation failed")
        return False


def instrument_logging() -> bool:
    """Inject trace_id / span_id into stdlib logging records."""
    if _INSTRUMENTED["logging"]:
        return True
    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().instrument(set_logging_format=False)
        _INSTRUMENTED["logging"] = True
        return True
    except ImportError:
        return False
    except Exception:
        logger.exception("logging instrumentation failed")
        return False


def instrument_all(*, app=None, engine=None, celery=None) -> dict:  # type: ignore[no-untyped-def]
    """
    Wire every instrumentation that has its dependencies available.

    Returns a dict mapping ``name -> bool`` so the caller can log
    which integrations actually activated.
    """
    if app is not None:
        instrument_app(app)
    if engine is not None:
        instrument_sqlalchemy(engine)
    instrument_asyncpg()
    instrument_redis()
    if celery is not None:
        instrument_celery(celery)
    instrument_logging()
    return dict(_INSTRUMENTED)


__all__ = [
    "instrument_app",
    "instrument_sqlalchemy",
    "instrument_asyncpg",
    "instrument_redis",
    "instrument_celery",
    "instrument_logging",
    "instrument_all",
] + [f"_{k}" for k in _INSTRUMENTED]
