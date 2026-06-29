"""
Sprint 3 R31 — Prometheus domain metrics.

A single ``CollectorRegistry`` (``REGISTRY``) owns all UniOps domain
metrics so they can be rendered through ``/metrics`` alongside the
HTTP-level metrics produced by ``prometheus-fastapi-instrumentator``
(or by FastAPI's own middleware if/when we migrate off).

Conventions:
  - Histograms for latency (seconds).  Bucket choice covers the
    realistic pipeline range (10ms … 30s).
  - Counters for cumulative events (failures, rejections, transitions,
    cache hits, business operations).
  - Gauges for in-progress values.
  - Cardinality of label values is bounded: ``tenant_id`` and ``state``
    are intentionally low-cardinality for production, but the helper
    functions accept arbitrary values and truncate very long strings
    to keep cardinality in check.

Tolerant: every helper is wrapped so a missing or broken Prometheus
client never crashes the calling pipeline.  ``render_latest`` returns
a valid ``bytes`` payload even when no metrics have been observed.
"""

from __future__ import annotations

import os
from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# A dedicated registry so we can render OUR metrics without pulling
# in the default registry (which may be polluted by other libraries).
REGISTRY = CollectorRegistry(auto_describe=True)


# ── Pipeline duration (latency) ────────────────────────────────────────────
PIPELINE_DURATION = Histogram(
    "uniops_pipeline_duration_seconds",
    "End-to-end pipeline evaluation duration.",
    labelnames=("pipeline", "state"),
    buckets=(
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
        30.0,
    ),
    registry=REGISTRY,
)


# ── Pipeline failure counter ───────────────────────────────────────────────
PIPELINE_FAILURES = Counter(
    "uniops_pipeline_failures_total",
    "Pipeline evaluations that raised an unhandled exception.",
    labelnames=("pipeline", "error_type"),
    registry=REGISTRY,
)


# ── Pipeline rejection counter ─────────────────────────────────────────────
PIPELINE_REJECTIONS = Counter(
    "uniops_pipeline_rejections_total",
    "Pipeline evaluations that produced a typed-domain rejection.",
    labelnames=("pipeline", "reason"),
    registry=REGISTRY,
)


# ── State machine transitions ──────────────────────────────────────────────
STATE_TRANSITIONS = Counter(
    "uniops_state_transitions_total",
    "Successful state transitions across the security engines.",
    labelnames=("entity", "from_state", "to_state"),
    registry=REGISTRY,
)


# ── Cache hits / misses ────────────────────────────────────────────────────
CACHE_HITS = Counter(
    "uniops_cache_hits_total",
    "Cache hits, partitioned by cache name.",
    labelnames=("cache",),
    registry=REGISTRY,
)

CACHE_MISSES = Counter(
    "uniops_cache_misses_total",
    "Cache misses, partitioned by cache name.",
    labelnames=("cache",),
    registry=REGISTRY,
)


# ── HTTP requests in progress ──────────────────────────────────────────────
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "uniops_http_requests_in_progress",
    "Currently in-flight HTTP requests.",
    registry=REGISTRY,
)


# ── Business operations (Celery tasks, scheduler jobs) ─────────────────────
BUSINESS_OPERATIONS = Counter(
    "uniops_business_operations_total",
    "Outcome of named business operations (Celery tasks, scheduler jobs).",
    labelnames=("operation", "outcome"),
    registry=REGISTRY,
)


# ── Helpers (tolerant: never raise) ────────────────────────────────────────
def _truncate(value: str, *, limit: int = 64) -> str:
    if value is None:
        return "unknown"
    s = str(value)
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


def _safe(metric_name: str, fn: Any) -> None:
    """Run ``fn`` swallowing every exception.  Prometheus failures are
    operational noise; they must never crash a pipeline."""
    try:
        fn()
    except Exception:  # pragma: no cover - non-fatal by design
        pass


def observe_pipeline_duration(
    *,
    pipeline: str,
    duration_seconds: float,
    state: str,
) -> None:
    _safe(
        "pipeline_duration",
        lambda: PIPELINE_DURATION.labels(
            pipeline=_truncate(pipeline),
            state=_truncate(state, limit=32),
        ).observe(max(duration_seconds, 0.0)),
    )


def observe_pipeline_failure(*, pipeline: str, error_type: str) -> None:
    _safe(
        "pipeline_failure",
        lambda: PIPELINE_FAILURES.labels(
            pipeline=_truncate(pipeline),
            error_type=_truncate(error_type, limit=64),
        ).inc(),
    )


def observe_pipeline_rejection(*, pipeline: str, reason: str) -> None:
    _safe(
        "pipeline_rejection",
        lambda: PIPELINE_REJECTIONS.labels(
            pipeline=_truncate(pipeline),
            reason=_truncate(reason, limit=64),
        ).inc(),
    )


def observe_state_transition(
    *,
    entity: str,
    from_state: str | None,
    to_state: str,
) -> None:
    _safe(
        "state_transition",
        lambda: STATE_TRANSITIONS.labels(
            entity=_truncate(entity, limit=32),
            from_state=_truncate(from_state or "none", limit=32),
            to_state=_truncate(to_state, limit=32),
        ).inc(),
    )


def observe_cache_hit(*, cache: str) -> None:
    _safe("cache_hit", lambda: CACHE_HITS.labels(cache=_truncate(cache, limit=32)).inc())


def observe_cache_miss(*, cache: str) -> None:
    _safe("cache_miss", lambda: CACHE_MISSES.labels(cache=_truncate(cache, limit=32)).inc())


def observe_business_operation(*, operation: str, outcome: str) -> None:
    _safe(
        "business_operation",
        lambda: BUSINESS_OPERATIONS.labels(
            operation=_truncate(operation, limit=64),
            outcome=_truncate(outcome, limit=16),
        ).inc(),
    )


def set_http_requests_in_progress(value: float) -> None:
    _safe(
        "http_requests_in_progress",
        lambda: HTTP_REQUESTS_IN_PROGRESS.set(max(value, 0.0)),
    )


def render_latest() -> bytes:
    """Render the UniOps registry in the Prometheus text exposition format."""
    try:
        return generate_latest(REGISTRY)
    except Exception:  # pragma: no cover - defensive
        return b""


def content_type() -> str:
    return CONTENT_TYPE_LATEST


# ── Optional Prometheus client (legacy ``app/utils/metrics.py`` re-exports)
# The legacy ``app/utils/metrics.py`` may import from here for backward
# compatibility.  We don't import it ourselves to keep the package
# dependency graph one-way.
_LEGACY_BRIDGE = os.getenv("UNIOPS_METRICS_LEGACY_BRIDGE", "1") == "1"


__all__ = [
    "REGISTRY",
    "PIPELINE_DURATION",
    "PIPELINE_FAILURES",
    "PIPELINE_REJECTIONS",
    "STATE_TRANSITIONS",
    "CACHE_HITS",
    "CACHE_MISSES",
    "HTTP_REQUESTS_IN_PROGRESS",
    "BUSINESS_OPERATIONS",
    "observe_pipeline_duration",
    "observe_pipeline_failure",
    "observe_pipeline_rejection",
    "observe_state_transition",
    "observe_cache_hit",
    "observe_cache_miss",
    "observe_business_operation",
    "set_http_requests_in_progress",
    "render_latest",
    "content_type",
] + ["_LEGACY_BRIDGE"]
