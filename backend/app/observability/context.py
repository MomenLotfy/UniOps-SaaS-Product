"""
Sprint 3 R30 — Observability Context.

Single source of truth for the four cross-cutting identifiers every
log line carries:

  - ``trace_id``     W3C traceparent trace ID (32 hex chars)
  - ``span_id``      W3C traceparent span ID (16 hex chars)
  - ``correlation_id`` UUID — links one logical operation across
                      pipeline stages, Celery tasks, and HTTP requests.
  - ``request_id``   8-hex request boundary ID — short enough for
                      logs, long enough to grep.
  - ``tenant_id``    multi-tenant scope (set by auth middleware).
  - ``user_id``      authenticated user (set by auth middleware).

We use ``contextvars.ContextVar`` because every layer in the project
runs inside asyncio (FastAPI handlers, Celery task coroutines,
scheduler job coroutines).  ``contextvars`` survive across ``await``
points without leaking across requests, exactly the property we need.

Helpers:

  - ``bind_context(**kwargs)``     Set fields on the current context.
  - ``unbind_context(*keys)``     Remove fields from the current context.
  - ``current_context()``         Snapshot the current context.
  - ``new_request_context()``     Mint a fresh context for a request/task.
"""

from __future__ import annotations

import contextvars
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

# ── ContextVars ────────────────────────────────────────────────────────────
_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
_span_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("span_id", default=None)
_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_id", default=None)
_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("user_id", default=None)


# ── Public API ─────────────────────────────────────────────────────────────
def new_request_id() -> str:
    """Mint a short 8-char request ID (greppable in logs)."""
    return uuid.uuid4().hex[:8]


def new_correlation_id() -> str:
    """Mint a fresh UUID4 correlation ID."""
    return str(uuid.uuid4())


def new_trace_id() -> str:
    """Mint a 32-hex-char trace ID (W3C traceparent shape)."""
    return uuid.uuid4().hex


def new_span_id() -> str:
    """Mint a 16-hex-char span ID."""
    return uuid.uuid4().hex[:16]


def bind_context(
    *,
    trace_id: str | None = None,
    span_id: str | None = None,
    correlation_id: str | None = None,
    request_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Set one or more fields on the current context."""
    if trace_id is not None:
        _trace_id.set(trace_id)
    if span_id is not None:
        _span_id.set(span_id)
    if correlation_id is not None:
        _correlation_id.set(correlation_id)
    if request_id is not None:
        _request_id.set(request_id)
    if tenant_id is not None:
        _tenant_id.set(tenant_id)
    if user_id is not None:
        _user_id.set(user_id)


def unbind_context(*keys: str) -> None:
    """Reset the listed keys on the current context."""
    mapping = {
        "trace_id": _trace_id,
        "span_id": _span_id,
        "correlation_id": _correlation_id,
        "request_id": _request_id,
        "tenant_id": _tenant_id,
        "user_id": _user_id,
    }
    for key in keys:
        var = mapping.get(key)
        if var is not None:
            var.set(None)


def current_context() -> dict[str, str | None]:
    """Snapshot the current context as a plain dict."""
    return {
        "trace_id": _trace_id.get(),
        "span_id": _span_id.get(),
        "correlation_id": _correlation_id.get(),
        "request_id": _request_id.get(),
        "tenant_id": _tenant_id.get(),
        "user_id": _user_id.get(),
    }


@contextmanager
def context_scope(**kwargs: Any) -> Iterator[None]:
    """
    Temporarily bind values, restoring the previous values on exit.

    Useful for background tasks that don't inherit the request context.
    """
    tokens = []
    for key, value in kwargs.items():
        var = _VARS.get(key)
        if var is None:
            continue
        tokens.append((var, var.set(value)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


_VARS = {
    "trace_id": _trace_id,
    "span_id": _span_id,
    "correlation_id": _correlation_id,
    "request_id": _request_id,
    "tenant_id": _tenant_id,
    "user_id": _user_id,
}


__all__ = [
    "bind_context",
    "unbind_context",
    "current_context",
    "new_request_id",
    "new_correlation_id",
    "new_trace_id",
    "new_span_id",
    "context_scope",
]
