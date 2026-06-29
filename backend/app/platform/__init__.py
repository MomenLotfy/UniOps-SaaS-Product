"""
Sprint 3 R35 — Shared Platform Components.

This package provides reusable abstractions used by the four security
engines (Decision / Strategy / Approval / Execution) and any future
engine.  They are NEW abstractions layered on top of the existing
engine-specific implementations; existing concrete classes keep their
public signatures and may opt into the bases for additional behavior.

The four layers:

- ``BaseCache`` — TTL cache with monotonic-clock TTL, explicit
  invalidation, and thread-safe store.  Designed to be Redis-swappable
  via ``serialize``/``deserialize`` hooks (no Redis wiring in Sprint 3).
- ``BaseLifecycleManager`` — generic state-transition pattern with
  explicit transition map, history row append, and metric emit.
- ``BaseAuditService`` — audit row template; concrete audit services
  use the same row schema.
- ``BaseStatisticsService`` — non-fatal recording helper; concrete
  statistics services inherit the swallowed-exception semantics.
- ``BasePipeline`` — async context manager that wraps
  ``TransactionManager.run_in_transaction`` so callers can opt in
  without changing existing pipelines.

Public APIs are deliberately small.  Each base is independently
tested; concrete modules continue to be tested against their own
signatures.
"""

from .base_audit_service import BaseAuditService
from .base_cache import BaseCache
from .base_lifecycle import BaseLifecycleManager, TransitionRule
from .base_pipeline import BasePipeline
from .base_statistics_service import BaseStatisticsService
from .thread_safe_registry import ThreadSafeRegistry

__all__ = [
    "BaseCache",
    "BaseLifecycleManager",
    "TransitionRule",
    "BaseAuditService",
    "BaseStatisticsService",
    "BasePipeline",
    "ThreadSafeRegistry",
]
