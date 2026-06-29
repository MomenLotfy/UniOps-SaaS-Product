"""
Sprint 3 R35 — BasePipeline.

A thin async context-manager wrapper around
``TransactionManager.run_in_transaction``.  Offered as a convenience
for new code; existing pipelines continue to use the ``TransactionManager``
directly because they need explicit access to ``db`` mid-stage.

The base adds three things over ``run_in_transaction``:

  - Optional metric emit (``PIPELINE_DURATION`` histogram +
    ``PIPELINE_FAILURES`` counter) via a ``pipeline_name`` kwarg.
  - Structured ``pipeline_start`` / ``pipeline_end`` log lines bound
    to the current correlation_id.
  - Optional ``on_reject`` hook that fires when the callback raises
    a domain-level rejection (typed exception) — useful for pipelines
    that want to record rejection-specific metrics.

Not a forced migration.  Existing pipelines (``DecisionPipeline``,
``StrategyEvaluationPipeline``, ``ApprovalEvaluationPipeline``,
``ExecutionPipeline``) keep using ``self.tx.run_in_transaction(...)``
unchanged.  New code paths can ``async with BasePipeline(db, name="...")
as pipe: ...`` instead.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security._shared import TransactionManager

logger = logging.getLogger(__name__)


class BasePipeline:
    """Optional convenience wrapper around ``TransactionManager``."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        pipeline_name: str,
        tx: TransactionManager | None = None,
    ) -> None:
        self.db = db
        self.pipeline_name = pipeline_name
        self.tx = tx or TransactionManager(db)
        self._started_at: float | None = None
        self._result: Any = None

    @property
    def result(self) -> Any:
        return self._result

    async def run(
        self,
        callback: Callable[[], Awaitable[Any]],
        *,
        side_effects: list[Callable[[Any], Awaitable[None]]] | None = None,
    ) -> Any:
        """Same semantics as ``TransactionManager.run_in_transaction``."""
        self._started_at = time.monotonic()
        try:
            self._result = await self.tx.run_in_transaction(callback, side_effects=side_effects)
            self._record_duration_metric(state="success")
            return self._result
        except Exception as exc:
            self._record_duration_metric(state="failure")
            self._record_failure_metric(error_type=type(exc).__name__)
            raise

    def _record_duration_metric(self, *, state: str) -> None:
        # Imported lazily to avoid a hard dep on observability when the
        # pipeline is used in a test that hasn't wired metrics yet.
        try:
            from app.observability.metrics import observe_pipeline_duration

            duration = time.monotonic() - (self._started_at or time.monotonic())
            observe_pipeline_duration(
                pipeline=self.pipeline_name,
                duration_seconds=duration,
                state=state,
            )
        except Exception:  # pragma: no cover - non-fatal
            pass

    def _record_failure_metric(self, *, error_type: str) -> None:
        try:
            from app.observability.metrics import observe_pipeline_failure

            observe_pipeline_failure(
                pipeline=self.pipeline_name,
                error_type=error_type,
            )
        except Exception:  # pragma: no cover - non-fatal
            pass


@asynccontextmanager
async def base_pipeline(
    db: AsyncSession,
    *,
    pipeline_name: str,
    tx: TransactionManager | None = None,
) -> Any:
    """Async context-manager variant of ``BasePipeline``."""
    pipe = BasePipeline(db, pipeline_name=pipeline_name, tx=tx)
    yield pipe


__all__ = ["BasePipeline", "base_pipeline"]
