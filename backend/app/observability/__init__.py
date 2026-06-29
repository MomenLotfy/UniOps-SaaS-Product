"""
Sprint 3 Observability package.

Exposes:
  - ``configure_structlog`` (R30)
  - ``init_tracing`` / ``instrument_app`` / etc. (R28)
  - ``init_sentry`` (R29)
  - ``metrics`` registry + helpers (R31)
  - ``validate_runtime_config`` (R34)
  - ContextVars (``correlation_id``, ``trace_id``, ``request_id``, ...)
    for use across FastAPI middleware, Celery signals, and pipeline
    stages.

All initialisation is environment-driven and tolerant of missing
optional dependencies — a missing OpenTelemetry package degrades to a
log line, never to a startup failure.
"""

from .metrics import (
    REGISTRY,
    observe_business_operation,
    observe_cache_hit,
    observe_cache_miss,
    observe_pipeline_duration,
    observe_pipeline_failure,
    observe_pipeline_rejection,
    observe_state_transition,
    render_latest,
    set_http_requests_in_progress,
)

__all__ = [
    "observe_pipeline_duration",
    "observe_pipeline_failure",
    "observe_pipeline_rejection",
    "observe_state_transition",
    "observe_cache_hit",
    "observe_cache_miss",
    "observe_business_operation",
    "set_http_requests_in_progress",
    "render_latest",
    "REGISTRY",
] + ["configure_structlog", "init_tracing", "init_sentry", "validate_runtime_config"]
