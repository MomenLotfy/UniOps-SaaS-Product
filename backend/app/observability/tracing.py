"""
Sprint 3 R28 — OpenTelemetry tracing.

`init_tracing()` configures the global ``TracerProvider`` with the
OTLP/gRPC exporter (env-gated via ``OTEL_EXPORTER_OTLP_ENDPOINT``).

Resource attributes (set from settings):
  - ``service.name``        from ``OTEL_SERVICE_NAME`` (default: settings.APP_NAME)
  - ``service.version``     from settings.APP_VERSION
  - ``deployment.environment`` from settings.APP_ENV

The exporter is wired to ``OTEL_EXPORTER_OTLP_ENDPOINT`` when set.
In dev / tests it is left disabled — the rest of the app still
functions; spans simply go nowhere.

The integration calls into ``instrumentation.py`` so callers don't
have to know which packages to wire.
"""

from __future__ import annotations

import logging
import os

from . import context as _ctx

logger = logging.getLogger(__name__)


_TRACER_PROVIDER: object | None = None


def init_tracing(
    *, service_name: str = "", service_version: str = "", environment: str = ""
) -> bool:
    """
    Initialise OpenTelemetry tracing.

    Returns ``True`` when the tracer is configured and exporter is
    reachable; ``False`` when OpenTelemetry is missing or the
    exporter is not configured.  Both outcomes are non-fatal —
    the rest of the app continues either way.
    """
    global _TRACER_PROVIDER
    if _TRACER_PROVIDER is not None:
        return True

    if os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true":
        logger.info("OpenTelemetry tracing disabled by OTEL_SDK_DISABLED=true")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.info("OpenTelemetry SDK not installed — tracing is a no-op")
        return False

    resource = Resource.create(
        {
            "service.name": service_name or os.getenv("OTEL_SERVICE_NAME", "uniops"),
            "service.version": service_version or os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
            "deployment.environment": environment or os.getenv("OTEL_ENVIRONMENT", "development"),
        }
    )
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OpenTelemetry OTLP exporter wired to %s", endpoint)
        except ImportError:
            logger.info("OTLP gRPC exporter not installed — spans stay in-process")
        except Exception:
            logger.exception("OpenTelemetry OTLP exporter failed to start")

    _TRACER_PROVIDER = provider
    return True


def current_trace_id_hex() -> str | None:
    """Return the active W3C trace_id (32 hex chars) or ``None``."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is None:
            return None
        ctx = span.get_span_context()
        if ctx is None or not ctx.is_valid:
            return None
        return f"{ctx.trace_id:032x}"
    except Exception:  # pragma: no cover - non-fatal
        return None


def current_span_id_hex() -> str | None:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is None:
            return None
        ctx = span.get_span_context()
        if ctx is None or not ctx.is_valid:
            return None
        return f"{ctx.span_id:016x}"
    except Exception:  # pragma: no cover - non-fatal
        return None


def bind_trace_context_from_active_span() -> None:
    """
    Mirror the active OTel span IDs into the structlog context.

    Called from ``LoggingMiddleware`` after each request handler runs.
    """
    trace_id = current_trace_id_hex()
    span_id = current_span_id_hex()
    if trace_id or span_id:
        _ctx.bind_context(trace_id=trace_id, span_id=span_id)


__all__ = [
    "init_tracing",
    "current_trace_id_hex",
    "current_span_id_hex",
    "bind_trace_context_from_active_span",
]
