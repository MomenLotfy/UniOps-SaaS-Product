"""
Sprint 3 R35 — BaseStatisticsService.

Common non-fatal recording helper for the four ``*StatisticsService``
classes.  The semantics are identical across the four services:

  - Catch every exception inside ``record_*``.
  - Log at ``logger.exception(...)`` and never re-raise.
  - Always use a deterministic ``correlation_id`` fallback so the
    NOT NULL ``DecisionBase.correlation_id`` constraint is satisfied.

Concrete services (Decision / Strategy / Approval / Execution
statistics) keep their method signatures and SQL row shapes; they
inherit ``safe_call`` to enforce the never-fail contract.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseStatisticsService:
    """Swallow-exception helper for statistics row writes."""

    @staticmethod
    def resolve_correlation_id(
        explicit: str | None,
        *,
        fallback: str,
    ) -> str:
        """Substitute a deterministic correlation_id placeholder when None."""
        if explicit:
            return explicit
        return fallback

    @staticmethod
    def safe_call(
        operation: Callable[[], T],
        *,
        label: str,
    ) -> T | None:
        """
        Run ``operation()``; on any exception, log and return ``None``.

        Never raises.  ``label`` is used in the log message so callers
        can identify which statistics write failed (e.g. ``"strategy
        record_evaluation"``).
        """
        try:
            return operation()
        except Exception:  # pragma: no cover - non-fatal by design
            logger.exception("statistics %s failed (non-fatal)", label)
            return None


__all__ = ["BaseStatisticsService"]
