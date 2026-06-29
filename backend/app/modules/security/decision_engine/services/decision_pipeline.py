"""
DecisionPipeline — 7-stage orchestration.

Sprint 1 R3+R4+R5 fixes:

  R3 — The engine no longer creates a new Decision.  The pipeline
       passes the *persisted* aggregate (created by DecisionManager)
       into ``engine.determine_decision``.  Status transitions go
       exclusively through ``DecisionManager.transition_to``.

  R4 — ``plans`` and ``reasons`` are now built against the persisted
       ``decision.id`` (the engine enforces this with a guard).
       No more orphan FKs.

  R5 — The rejection path now commits the audit history BEFORE
       rolling back the working transaction.  Previously the
       rejection transition was rolled back along with everything
       else, erasing the very history row that justified the
       rejection.  Now: flush + commit history; then rollback the
       in-flight decision; then re-raise.

Sprint 2 R16 (consistency):
  The pipeline delegates commit / rollback / post-commit side effects
  to ``TransactionManager.run_in_transaction`` so the decision engine
  uses the SAME contract as the strategy / approval / execution
  engines.  Statistics updates are best-effort post-commit side effects
  and never fail the call.

  The rejection-with-history flow remains a special case: R5 commits
  the rejection audit row AFTER rolling back the failing work, so it
  is implemented as an ``on_error`` callback of
  ``run_in_transaction`` rather than inside the main body.
"""
from __future__ import annotations

import logging
import time
from typing import Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security._shared import TransactionManager
from .context_builder import DecisionContextBuilder
from .decision_validator import DecisionValidator
from .decision_engine import DecisionEngine
from .decision_manager import DecisionManager
from .statistics_service import StatisticsService
from ..constants import DecisionState

logger = logging.getLogger(__name__)


class DecisionPipeline:
    """
    Orchestrates the sequential stages of creating a security decision.
    """

    def __init__(
        self,
        db: AsyncSession,
        context_builder: DecisionContextBuilder,
        validator: DecisionValidator,
        engine: DecisionEngine,
        manager: DecisionManager,
        stats_service: StatisticsService,
    ):
        self.db = db
        self.context_builder = context_builder
        self.validator = validator
        self.engine = engine
        self.manager = manager
        self.stats_service = stats_service
        self.tx = TransactionManager(db)

    # ── Public entry point ──────────────────────────────────────────────
    async def execute(
        self,
        tenant_id: str,
        finding_id: str,
        correlation_id: str,
    ) -> Any:
        """
        Runs the full pipeline from Context Build to Statistics Update.
        Returns the persisted :class:`Decision``.

        R16 contract (mirrors Strategy / Approval / Execution):
          - single ``commit`` after Stage 5 persistence succeeds;
          - ``rollback`` on any exception escaping the body;
          - statistics + audit recorded as best-effort post-commit
            side effects via ``TransactionManager.run_in_transaction``.

        R5 contract:
          On validator rejection the pipeline commits the decision
          row + history up to the rejection point in a fresh
          transaction, then transitions the persisted decision to
          REJECTED in another fresh transaction — so the rejection
          audit trail survives while the rejected work-in-progress is
          rolled back.  The original ``Decision`` row is committed
          (with ``status=VALIDATING`` or ``status=CREATED``) so a
          follow-up ``transition_to(REJECTED)`` finds it.
        """
        start_time = time.monotonic()
        decision_id_holder: List[str] = []
        resolution_holder: List[Any] = []
        duration_holder: List[float] = []

        async def _stages() -> Any:
            # ── Stage 1: Create Decision Entity ──────────────────────────
            # R3: the aggregate is created and persisted here, owned by
            # the manager.  The engine NEVER creates one.
            decision = await self.manager.create_decision(
                tenant_id, correlation_id, ""
            )
            decision_id_holder.append(decision.id)

            # ── Stage 2: Context Build ─────────────────────────────────
            await self.manager.transition_to(
                decision.id, DecisionState.CONTEXT_BUILDING
            )
            context = await self.context_builder.build_context(
                tenant_id, finding_id, correlation_id
            )
            self.db.add(context)
            await self.db.flush()
            decision.context_id = context.id

            # ── Stage 3: Validation ───────────────────────────────────
            await self.manager.transition_to(
                decision.id, DecisionState.VALIDATING
            )
            is_valid, error = await self.validator.validate_request(
                tenant_id, finding_id
            )
            if not is_valid:
                # R5: commit the decision + history up to this point
                # so the rejection transition can find the row, then
                # raise so the on_error callback finalises the
                # REJECTED transition + statistics.
                await self.db.commit()
                raise _DecisionRejected(error or "validator rejected request")

            # ── Stage 4: Decision Creation (Rule + Policy engines) ──
            decision_obj, plans, reasons, resolution = await self.engine.determine_decision(
                decision, context
            )
            assert decision_obj is decision, "engine must return the same aggregate"

            # R3: state transition goes through manager, never direct.
            await self.manager.transition_to(decision.id, DecisionState.READY)

            # ── Stage 5: Persistence ────────────────────────────────
            # R4: plans[0].id was generated client-side; add it now.
            # Guard: NO_ACTION result legitimately returns [].
            if plans:
                self.db.add(plans[0])
            for r in reasons:
                self.db.add(r)

            resolution_holder.append(resolution)
            duration_holder.append((time.monotonic() - start_time) * 1000.0)
            return decision

        async def _post_commit(decision: Any) -> None:
            # ── Stage 6: Statistics Update (best-effort) ────────────
            try:
                duration_ms = duration_holder[0] if duration_holder else 0.0
                await self.stats_service.record_decision_stats(
                    tenant_id, DecisionState.READY, duration_ms,
                    correlation_id=decision_id_holder[-1],
                )
                res = resolution_holder[0] if resolution_holder else None
                if res and getattr(res, "policy_id", "N/A") != "N/A":
                    await self.stats_service.record_policy_stats(
                        policy_id=res.policy_id,
                        duration_ms=duration_ms,
                        was_overridden=getattr(res, "overridden", False),
                        tenant_id=tenant_id,
                        correlation_id=decision_id_holder[-1],
                    )
            except Exception:  # pragma: no cover - non-fatal
                logger.exception("decision statistics update failed (non-fatal)")

        try:
            return await self.tx.run_in_transaction(
                _stages,
                side_effects=[_post_commit],
                pipeline="decision",
            )
        except _DecisionRejected as exc:
            # R5 path: the validator already committed the decision +
            # context + history up to the rejection point.  Now
            # transition the persisted decision to REJECTED in a fresh
            # transaction and record REJECTED statistics.
            decision_id = decision_id_holder[-1] if decision_id_holder else None
            if decision_id is not None:
                await self._finalise_rejection(
                    decision_id=decision_id,
                    tenant_id=tenant_id,
                    reason=str(getattr(exc, "reason", exc)),
                    started=start_time,
                )
            raise

    # ── Rejection finaliser (R5) ────────────────────────────────────────
    async def _finalise_rejection(
        self,
        *,
        decision_id: str,
        tenant_id: str,
        reason: str,
        started: float,
    ) -> None:
        """
        R5 — after the validator rejects the request and the
        pipeline has committed the decision + history up to the
        rejection point, this method transitions the persisted
        decision to REJECTED in a fresh transaction so the
        rejection audit trail survives.

        Sequence:
          1. Re-open a fresh transaction and transition the decision
             to REJECTED — this writes a DecisionHistory row.
          2. Commit the REJECTED transition.
          3. Record statistics on the now-committed REJECTED state.
        """
        # Step 1 + 2: re-enter a clean transaction to record history.
        try:
            await self.manager.transition_to(
                decision_id, DecisionState.REJECTED, reason=reason
            )
            await self.db.commit()
        except Exception:  # pragma: no cover - non-fatal audit failure
            logger.exception(
                "failed to commit REJECTED history for decision=%s", decision_id
            )
            try:
                await self.db.rollback()
            except Exception:
                pass

        # Step 3: statistics on the now-committed state.
        try:
            duration_ms = (time.monotonic() - started) * 1000.0
            await self.stats_service.record_decision_stats(
                tenant_id, DecisionState.REJECTED, duration_ms,
                correlation_id=decision_id,
            )
        except Exception:  # pragma: no cover - non-fatal
            logger.exception("failed to record REJECTED statistics")


class _DecisionRejected(Exception):
    """Internal signal raised inside the pipeline body to trigger the
    R5 commit-history-then-rollback flow without losing context.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


__all__ = ["DecisionPipeline"]
