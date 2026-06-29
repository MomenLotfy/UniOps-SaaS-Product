"""
Sprint 3 R30 — Structured JSON log formatter.

A single ``JSONRenderer`` that produces one JSON object per log line.
Each object carries the R30-required fields plus the project's own
observability context (trace_id / span_id / correlation_id / request_id /
tenant_id / user_id).

Why a single class instead of structlog's built-in ``JSONRenderer``?
  - The project already runs loguru.  The renderer is therefore the
    *output* stage of structlog; the rest of the structlog pipeline
    (level, time, context, etc.) is wired in ``logging.py``.
  - A single class keeps the JSON shape independent of structlog's
    internal version (we have a 24.x version pinned but the API has
    drifted in the past).
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from typing import Any

from . import context as _ctx


def _coerce(value: Any) -> Any:
    """Stringify non-primitive values defensively."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def render_json(
    *,
    level: str,
    event: str,
    timestamp: _dt.datetime,
    module: str,
    service: str,
    environment: str,
    version: str,
    extra: dict[str, Any] | None = None,
) -> str:
    """
    Produce the canonical JSON log line.

    ``extra`` may contain any caller-supplied fields.  Known
    context fields are merged into the top level so log aggregators
    can index them directly.
    """
    ctx = _ctx.current_context()
    payload: dict[str, Any] = {
        "timestamp": timestamp.isoformat(),
        "level": level.upper(),
        "event": str(event),
        "module": module,
        "service": service,
        "environment": environment,
        "version": version,
        # Observability context
        "trace_id": ctx.get("trace_id"),
        "span_id": ctx.get("span_id"),
        "correlation_id": ctx.get("correlation_id"),
        "request_id": ctx.get("request_id"),
        "tenant_id": ctx.get("tenant_id"),
        "user_id": ctx.get("user_id"),
    }
    if extra:
        for k, v in extra.items():
            payload[k] = _coerce(v)
    return json.dumps(payload, default=str, ensure_ascii=False)


__all__ = ["render_json"]


def bind_log_level(logger: logging.Logger) -> str:
    return logging.getLevelName(logger.getEffectiveLevel())
