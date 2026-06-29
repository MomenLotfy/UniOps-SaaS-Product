"""
Sprint 3 R31 — Prometheus legacy bridge.

The previous version of this module declared a handful of
prometheus_client primitives that were never imported anywhere.  We
re-export the unified metric primitives from
``app.observability.metrics`` so any legacy import
(``from app.utils.metrics import http_requests_total``) continues to
work.

New code should import from ``app.observability.metrics`` directly.
"""
from __future__ import annotations

from app.observability.metrics import (  # noqa: F401
    observe_pipeline_duration,
    observe_pipeline_failure,
    observe_pipeline_rejection,
    observe_state_transition,
    observe_cache_hit,
    observe_cache_miss,
    observe_business_operation,
    set_http_requests_in_progress,
    render_latest,
    REGISTRY,
    PIPELINE_DURATION,
    PIPELINE_FAILURES,
    PIPELINE_REJECTIONS,
    STATE_TRANSITIONS,
    CACHE_HITS,
    CACHE_MISSES,
    HTTP_REQUESTS_IN_PROGRESS,
    BUSINESS_OPERATIONS,
)


# ── Legacy names kept for backward compatibility ─────────────────────────────
class _LegacyCounterShim:
    """Backward-compatible shim for legacy ``.inc()`` / ``.labels(...)``."""

    def __init__(self, *, name: str, labelnames=()):
        self._name = name
        self._labelnames = tuple(labelnames)

    def labels(self, **kwargs):
        # We don't need to record legacy counters — new code uses
        # ``observe_*`` helpers.  The shim returns itself so legacy
        # ``counter.labels(...).inc()`` chains compile.
        return self

    def inc(self, *args, **kwargs):
        return None


http_requests_total = _LegacyCounterShim(
    name="uniops_http_requests_total",
    labelnames=("method", "endpoint", "status"),
)
http_request_duration = _LegacyCounterShim(
    name="uniops_http_request_duration_seconds",
    labelnames=("method", "endpoint"),
)
active_users = _LegacyCounterShim(name="uniops_active_users")
active_websockets = _LegacyCounterShim(name="uniops_active_websockets")