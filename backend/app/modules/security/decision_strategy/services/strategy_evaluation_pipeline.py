"""
Strategy Evaluation Pipeline.

7-stage pipeline that orchestrates the engine + persistence + statistics
+ history.  Mirrors `DecisionPipeline` in the sibling decision_engine
module.

Stages:
  1. Discovery          — load Decision + aggregated Context
  2. Statistics Load    — pull aggregate metrics for the tenant
  3. Candidate Build    — resolver + factory + validator + scoring
  4. Ranking            — comparator-based, deterministic
  5. Selection          — top-valid, NO_ACTION fallback
  6. Persistence        — write DecisionStrategy + supporting rows
  7. Statistics Update  — record evaluation duration + rejection counts

Transaction Contract (Sprint 2 R16):
  - The caller owns the outer transaction boundary.
  - Pipeline guarantees: ``commit()`` is invoked exactly once after a
    successful Stage 6 persistence; ``rollback()`` is invoked on any
    exception that escapes the body.
  - Stage 7 (statistics) is best-effort — failures are logged and
    never fail the outer call.  ``TransactionManager.run_in_transaction``
    enforces this semantics.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.modules.security._shared import TransactionManager
from .strategy_engine import DecisionStrategyEngine
from .strategy_interfaces import StrategyEvaluationResult
from .strategy_repository import DecisionStrategyRepository
from .strategy_statistics_service import DecisionStrategyStatisticsService

logger = logging.getLogger(__name__)


class StrategyEvaluationPipeline:
    """
    7-stage strategy evaluation pipeline.
    """

    def __init__(
        self,
        db: AsyncSession,
        engine: Optional[DecisionStrategyEngine] = None,
    ) -> None:
        self.db = db
        self.engine = engine or DecisionStrategyEngine()
        self.repository = DecisionStrategyRepository(db)
        self.statistics = DecisionStrategyStatisticsService(db)
        self.tx = TransactionManager(db)

    async def run(
        self,
        decision: Any,
        context: Any,
        tenant_id: Optional[str] = None,
    ) -> StrategyEvaluationResult:
        """
        Execute all 7 stages under a single transaction.

        R16 contract: commit once after Stage 6 succeeds; rollback on
        any exception.  Stage 7 statistics are best-effort post-commit
        side effects — they never fail the call.
        """
        if tenant_id is None:
            tenant_id = getattr(context, "tenant_id", None) or getattr(decision, "tenant_id", "default")

        async def _stages() -> StrategyEvaluationResult:
            # ── Stage 1: Discovery ─────────────────────────────────────
            logger.debug("pipeline[1/7] discovery tenant=%s decision=%s", tenant_id, decision.id)
            if decision is None:
                raise ValidationError("Decision is required", field="decision")
            if context is None:
                raise ValidationError("DecisionContext is required", field="context")

            # ── Stage 2: Statistics Load ───────────────────────────────
            logger.debug("pipeline[2/7] statistics_load tenant=%s", tenant_id)
            try:
                statistics = await self.repository.get_statistics(tenant_id)
            except Exception:  # pragma: no cover - read-only, non-fatal
                statistics = {}

            # ── Stage 3: Candidate Build ───────────────────────────────
            logger.debug("pipeline[3/7] candidate_build decision=%s", decision.id)
            result = self.engine.evaluate(decision, context, statistics=statistics, tenant_id=tenant_id)

            if result.winner is None:
                logger.warning("pipeline no candidate selected decision=%s", decision.id)
                return result

            # ── Stage 4: Ranking ───────────────────────────────────────
            logger.debug(
                "pipeline[4/7] ranking decision=%s top=%s score=%.3f",
                decision.id,
                result.winner.candidate_type.value,
                result.winner.composite_score,
            )

            # ── Stage 5: Selection ─────────────────────────────────────
            logger.debug(
                "pipeline[5/7] selection decision=%s winner=%s",
                decision.id,
                result.winner.candidate_type.value,
            )

            # ── Stage 6: Persistence ───────────────────────────────────
            logger.debug("pipeline[6/7] persistence decision=%s", decision.id)
            strategy_row = await self.engine.persist_winner(result, self.db, context=context)
            # R27: winning_strategy_id must be set BEFORE save_evaluation,
            # because StrategyRanking / StrategyHistory / StrategyEvaluation
            # FK back to security_decision_strategies.id.
            result.winning_strategy_id = strategy_row.id
            await self.engine.persist_alternatives(result, strategy_row.id, self.db)
            await self.repository.save_evaluation(result)

            return result

        async def _stats(result: StrategyEvaluationResult) -> None:
            # ── Stage 7: Statistics Update ───────────────────────────
            logger.debug("pipeline[7/7] statistics_update decision=%s", decision.id)
            try:
                if result.winner is None:
                    return
                await self.statistics.record_evaluation(
                    tenant_id=tenant_id,
                    strategy_type=result.winner.candidate_type,
                    duration_ms=result.evaluation_duration_ms,
                )
                for c in result.candidates:
                    if not c.is_valid:
                        await self.statistics.record_rejection(
                            tenant_id=tenant_id,
                            strategy_type=c.candidate_type,
                        )
            except Exception:  # pragma: no cover - non-fatal
                logger.exception("statistics update failed (non-fatal)")

        return await self.tx.run_in_transaction(
            _stages,
            side_effects=[_stats],
            pipeline="strategy",
        )