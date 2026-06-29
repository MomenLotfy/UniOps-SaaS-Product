"""
HTTP logging middleware.

Sprint 3 R30 extension:
  - Reads inbound ``X-Request-ID`` / ``traceparent`` headers when
    present (lets the caller propagate a trace from upstream).
  - Mints a fresh ``correlation_id`` if none is present so every
    request has one.
  - Binds everything onto the ``app.observability.context`` ContextVars
    for the duration of the request.
  - Returns ``X-Request-ID`` + ``X-Correlation-Id`` + ``X-Trace-Id``
    headers on the response.
"""
from __future__ import annotations

import time
import uuid
import re

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logger import logger
from app.observability import context as obs_context


_TRACEPARENT_RE = re.compile(r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


def _parse_traceparent(value: str | None):
    """Return ``(trace_id, span_id)`` from a W3C traceparent or ``(None, None)``."""
    if not value:
        return None, None
    m = _TRACEPARENT_RE.match(value.strip())
    if not m:
        return None, None
    return m.group(2), m.group(3)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Inbound or minted identifiers
        inbound_request_id = request.headers.get("X-Request-ID")
        request_id = inbound_request_id or uuid.uuid4().hex[:8]
        inbound_correlation = request.headers.get("X-Correlation-Id")
        correlation_id = inbound_correlation or str(uuid.uuid4())
        trace_id, span_id = _parse_traceparent(request.headers.get("traceparent"))

        obs_context.bind_context(
            request_id=request_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            span_id=span_id,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "[%s] %s %s -> %s (%.2fms)",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-Id"] = correlation_id
            if trace_id:
                response.headers["X-Trace-Id"] = trace_id
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "[%s] %s %s -> ERR (%.2fms): %s",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
                exc,
            )
            raise
        finally:
            obs_context.unbind_context(
                "request_id",
                "correlation_id",
                "trace_id",
                "span_id",
                "tenant_id",
                "user_id",
            )