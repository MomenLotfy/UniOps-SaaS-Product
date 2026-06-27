"""
Decision Strategy Repository.

Thin SQLAlchemy 2.x implementation of `IStrategyRepository`.
All read paths are tenant-scoped.  All write paths return ORM objects —
the caller owns the transaction.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import StrategyState, StrategyType
from ..models.strategy import (
    DecisionStrategy,
    StrategyEvaluation,
    StrategyHistory,
    StrategyRanking,
    StrategyStatistics,
    StrategyVersion,
)
from .strategy_interfaces import IStrategyRepository, StrategyEvaluationResult


class DecisionStrategyRepository(IStrategyRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Writes ─────────────────────────────────────────────────────────
    async def save_evaluation(self, result: StrategyEvaluationResult) -> StrategyEvaluation:
        """
        Persist the winning DecisionStrategy + all supporting rows in
        a single transaction (delegated to caller).  Returns the
        StrategyEvaluation row.
        """
        win = result.winner
        # Already added by the engine — flush to populate id
        await self.db.flush()

        evaluation = StrategyEvaluation(
            tenant_id=win.tenant_id,
            decision_id=result.decision_id,
            winning_strategy_id=win.id,
            candidate_count=len(result.candidates),
            valid_count=sum(1 for c in result.candidates if c.is_valid),
            rejected_count=sum(1 for c in result.candidates if not c.is_valid),
            selected_type=win.candidate_type,
            composite_score=win.composite_score,
            feasibility_score=win.feasibility_score,
            risk_score=win.risk_score,
            ranking_stable=result.ranking_stable,
            evaluation_duration_ms=result.evaluation_duration_ms,
            correlation_id=win.correlation_id,
            trace_id=win.trace_id,
        )
        self.db.add(evaluation)

        # Persist StrategyRanking rows (one per candidate)
        for c in result.candidates:
            ranking = StrategyRanking(
                tenant_id=win.tenant_id,
                strategy_id=win.id,
                evaluation_id=None,  # set after flush
                candidate_type=c.candidate_type,
                rank=c.rank,
                composite_score=c.composite_score,
                feasibility_score=c.feasibility_score,
                is_valid=c.is_valid,
                rejection_reason=c.rejection_reason,
                correlation_id=win.correlation_id,
                trace_id=win.trace_id,
            )
            self.db.add(ranking)

        await self.db.flush()
        # Bind evaluation_id onto rankings now that we have it
        unbound = await self.db.execute(
            select(StrategyRanking).where(
                StrategyRanking.strategy_id == win.id,
                StrategyRanking.evaluation_id.is_(None),
            )
        )
        for ranking_row in unbound.scalars().all():
            ranking_row.evaluation_id = evaluation.id

        # Persist initial history entry for the strategy
        hist = StrategyHistory(
            tenant_id=win.tenant_id,
            strategy_id=win.id,
            from_state=None,
            to_state=win.state,
            changed_by="system",
            change_reason="Initial strategy evaluation persisted",
            correlation_id=win.correlation_id,
            trace_id=win.trace_id,
        )
        self.db.add(hist)
        await self.db.flush()

        return evaluation

    # ── Reads ──────────────────────────────────────────────────────────
    async def get_by_id(self, strategy_id: str) -> Optional[DecisionStrategy]:
        result = await self.db.execute(
            select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
        )
        return result.scalar_one_or_none()

    async def list_for_tenant(
        self,
        tenant_id: str,
        state: Optional[StrategyState] = None,
        strategy_type: Optional[StrategyType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DecisionStrategy]:
        stmt = select(DecisionStrategy).where(DecisionStrategy.tenant_id == tenant_id)
        if state is not None:
            stmt = stmt.where(DecisionStrategy.state == state)
        if strategy_type is not None:
            stmt = stmt.where(DecisionStrategy.strategy_type == strategy_type)
        stmt = stmt.order_by(desc(DecisionStrategy.composite_score)).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_history(self, strategy_id: str) -> List[StrategyHistory]:
        result = await self.db.execute(
            select(StrategyHistory)
            .where(StrategyHistory.strategy_id == strategy_id)
            .order_by(StrategyHistory.created_at)
        )
        return list(result.scalars().all())

    async def list_versions(self, strategy_id: str) -> List[StrategyVersion]:
        result = await self.db.execute(
            select(StrategyVersion)
            .where(StrategyVersion.strategy_id == strategy_id)
            .order_by(StrategyVersion.version_number)
        )
        return list(result.scalars().all())

    async def get_statistics(self, tenant_id: str) -> dict:
        """
        Tenant-wide strategy metrics.  Returns a plain dict to avoid
        ORM coupling at the API boundary.
        """
        # Per-type counts
        type_rows = await self.db.execute(
            select(
                DecisionStrategy.strategy_type,
                func.count(DecisionStrategy.id).label("count"),
                func.avg(DecisionStrategy.composite_score).label("avg_score"),
                func.avg(DecisionStrategy.feasibility_score).label("avg_feas"),
            )
            .where(DecisionStrategy.tenant_id == tenant_id)
            .group_by(DecisionStrategy.strategy_type)
        )
        per_type = {
            str(row.strategy_type): {
                "count": int(row.count),
                "avg_composite_score": float(row.avg_score or 0.0),
                "avg_feasibility_score": float(row.avg_feas or 0.0),
            }
            for row in type_rows
        }

        # Per-state counts
        state_rows = await self.db.execute(
            select(DecisionStrategy.state, func.count(DecisionStrategy.id))
            .where(DecisionStrategy.tenant_id == tenant_id)
            .group_by(DecisionStrategy.state)
        )
        per_state = {str(row[0]): int(row[1]) for row in state_rows}

        # Totals
        total_row = await self.db.execute(
            select(func.count(DecisionStrategy.id))
            .where(DecisionStrategy.tenant_id == tenant_id)
        )
        total = int(total_row.scalar_one() or 0)

        # Avg evaluation duration from StrategyStatistics rows
        eval_rows = await self.db.execute(
            select(
                func.avg(StrategyStatistics.avg_duration_ms).label("avg_dur"),
                func.sum(StrategyStatistics.count).label("eval_total"),
            )
            .where(StrategyStatistics.tenant_id == tenant_id)
        )
        eval_row = eval_rows.first()
        avg_dur = float(eval_row.avg_dur or 0.0) if eval_row else 0.0
        eval_total = int(eval_row.eval_total or 0) if eval_row else 0

        return {
            "tenant_id": tenant_id,
            "total_strategies": total,
            "per_type": per_type,
            "per_state": per_state,
            "evaluation_total": eval_total,
            "avg_evaluation_duration_ms": avg_dur,
        }