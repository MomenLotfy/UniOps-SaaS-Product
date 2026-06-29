"""
Transaction Manager — Sprint 2 R16.

Lightweight helper that codifies the project's transaction boundary
semantics for every engine pipeline.

Why a helper instead of inline ``async with session.begin()``?
  - The decision pipeline must commit some rows (history) BEFORE
    rolling back others (the failing decision).  `with_transaction`
    supports that via the ``preserved_callbacks`` parameter.
  - Different engines raise different typed exceptions that should
    map to different rollback strategies.
  - Audit / statistics writes are best-effort and must never fail
    the transaction; the helper runs them post-commit.

Sprint 3 R31: optionally emits Prometheus ``PIPELINE_DURATION`` /
``PIPELINE_FAILURES`` metrics when a ``pipeline`` keyword is supplied.
The metric calls are best-effort and never fail the caller.

Every pipeline in the decision / strategy / approval / execution modules
delegates its commit + rollback sequencing to this class.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UniOpsException

logger = logging.getLogger(__name__)


class TransactionManager:
    """Coordinator for commit / rollback + post-commit side effects."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def commit(self) -> None:
        """Flush + commit the current transaction."""
        await self.db.commit()

    async def rollback(self) -> None:
        """Discard any pending changes."""
        try:
            await self.db.rollback()
        except Exception:  # pragma: no cover - defensive
            logger.exception("rollback failed")

    async def commit_or_rollback(
        self,
        *,
        on_error: Callable[[BaseException], Awaitable[None]] | None = None,
    ) -> bool:
        """
        Commit if no exception is currently active; rollback if there is one.
        Returns ``True`` on clean commit, ``False`` after a rollback.
        """
        try:
            await self.db.commit()
            return True
        except UniOpsException:
            await self.rollback()
            if on_error is not None:
                try:
                    await on_error(_last_exc())  # type: ignore[name-defined]
                except Exception:  # pragma: no cover - defensive
                    logger.exception("on_error handler raised")
            return False
        except Exception as exc:
            await self.rollback()
            logger.exception("commit failed")
            if on_error is not None:
                try:
                    await on_error(exc)
                except Exception:  # pragma: no cover - defensive
                    logger.exception("on_error handler raised")
            return False

    async def run_in_transaction(
        self,
        callback: Callable[[], Awaitable[Any]],
        *,
        side_effects: list[Callable[[Any], Awaitable[None]]] | None = None,
        pipeline: str | None = None,
    ) -> Any:
        """
        Run ``callback()`` inside a transaction.  Commit on success;
        rollback on any exception.  Run ``side_effects`` (e.g. statistics,
        audit) only after a successful commit — they never fail the call.

        Sprint 3 R31: ``pipeline`` is an optional name used to emit
        ``PIPELINE_DURATION`` + ``PIPELINE_FAILURES`` metrics.  Missing
        or broken observability does not affect the transaction.

        Returns the value returned by ``callback``.
        """
        started = time.monotonic()
        try:
            result = await callback()
            await self.db.commit()
        except UniOpsException:
            await self.rollback()
            if pipeline:
                self._emit_metric(pipeline, started, "failure")
                self._emit_failure(pipeline, type(_last_exc()).__name__)
            raise
        except Exception:
            await self.rollback()
            if pipeline:
                self._emit_metric(pipeline, started, "failure")
                self._emit_failure(pipeline, type(_last_exc()).__name__)
            raise

        if side_effects:
            for effect in side_effects:
                try:
                    await effect(result)
                except Exception:  # pragma: no cover - non-fatal
                    logger.exception("post-commit side effect failed")
        if pipeline:
            self._emit_metric(pipeline, started, "success")
        return result

    @staticmethod
    def _emit_metric(pipeline: str, started: float, state: str) -> None:
        try:
            from app.observability.metrics import observe_pipeline_duration

            observe_pipeline_duration(
                pipeline=pipeline,
                duration_seconds=time.monotonic() - started,
                state=state,
            )
        except Exception:  # pragma: no cover - non-fatal
            pass

    @staticmethod
    def _emit_failure(pipeline: str, error_type: str) -> None:
        try:
            from app.observability.metrics import observe_pipeline_failure

            observe_pipeline_failure(pipeline=pipeline, error_type=error_type)
        except Exception:  # pragma: no cover - non-fatal
            pass


@asynccontextmanager
async def transactional_session(db: AsyncSession) -> Any:
    """
    Async context manager: yields the session; commits on clean exit,
    rolls back on exception.
    """
    try:
        yield db
    except Exception:
        try:
            await db.rollback()
        except Exception:  # pragma: no cover - defensive
            logger.exception("rollback failed inside transactional_session")
        raise
    else:
        try:
            await db.commit()
        except Exception:  # pragma: no cover - defensive
            logger.exception("commit failed inside transactional_session")
            raise


def _last_exc() -> BaseException:
    """Placeholder for callers that don't import sys.exc_info directly."""
    import sys

    return sys.exc_info()[1] or RuntimeError("unknown")


__all__ = ["TransactionManager", "transactional_session"]
