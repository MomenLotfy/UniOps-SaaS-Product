"""
Decision Strategy Repository.

Thin SQLAlchemy 2.x implementation of `IStrategyRepository`.
All read paths are tenant-scoped.  All write paths return ORM objects —
the caller owns the transaction.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..constants import StrategyState, StrategyType
from ..models.strategy import (
    DecisionStrategy,
    StrategyCandidate,
    StrategyEvaluation,
    StrategyHistory,
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

        R27 contract: ``winning_strategy_id`` is the ``DecisionStrategy.id``
        populated by ``engine.persist_winner`` (which is called BEFORE this
        method in the pipeline).  The in-memory ``StrategyCandidateData``
        carries no ORM id, so we cannot rely on ``win.id`` here.
        """
        win = result.winner
        winning_strategy_id = result.winning_strategy_id
        if winning_strategy_id is None:
            raise ValueError(
                "save_evaluation called before winning_strategy_id was set; "
                "ensure engine.persist_winner(...) ran first and assigned "
                "result.winning_strategy_id."
            )
        # Already added by the engine — flush to populate id
        await self.db.flush()

        # Resolve correlation_id once so we never persist NULL into a
        # NOT NULL column.  Fall back to the decision-derived placeholder
        # when the in-memory candidate has no correlation_id.
        effective_corr = (
            win.correlation_id
            or getattr(win, "decision_id", None)
            and f"strategy-evaluation:{win.decision_id}"
            or f"strategy-evaluation:{result.decision_id}"
        )

        evaluation = StrategyEvaluation(
            tenant_id=win.tenant_id,
            decision_id=result.decision_id,
            selected_strategy_id=winning_strategy_id,
            candidate_count=len(result.candidates),
            rejected_count=sum(1 for c in result.candidates if not c.is_valid),
            duration_ms=result.evaluation_duration_ms,
            correlation_id=effective_corr,
            trace_id=win.trace_id,
        )
        self.db.add(evaluation)

        # Persist initial history entry for the strategy
        # R27: in-memory StrategyCandidateData does not carry a ``state``
        # field — the only stateful thing is the DecisionStrategy row
        # we just persisted.  Default to ``SELECTED`` here; lifecycle
        # transitions are tracked separately.
        from ..constants import StrategyState
        initial_state = StrategyState.SELECTED
        hist = StrategyHistory(
            tenant_id=win.tenant_id,
            strategy_id=winning_strategy_id,
            from_state=None,
            to_state=initial_state,
            changed_by="system",
            change_reason="Initial strategy evaluation persisted",
            correlation_id=effective_corr,
            trace_id=win.trace_id,
        )
        self.db.add(hist)
        await self.db.flush()

        return evaluation

    # ── Reads ──────────────────────────────────────────────────────────
    async def get_by_id(self, strategy_id: str) -> Optional[DecisionStrategy]:
        # Sprint 2 R17: eagerly load child collections so route handlers can
        # access ``strategy.candidates`` / ``strategy.scores`` / ``strategy.reasons``
        # / ``strategy.constraints`` / ``strategy.requirements`` / ``strategy.metadata``
        # without triggering lazy loads on a detached session.
        stmt = (
            select(DecisionStrategy)
            .where(DecisionStrategy.id == strategy_id)
            .options(
                selectinload(DecisionStrategy.candidates).selectinload(StrategyCandidate.scores),
                selectinload(DecisionStrategy.candidates).selectinload(StrategyCandidate.reasons),
                selectinload(DecisionStrategy.candidates).selectinload(StrategyCandidate.constraints),
                selectinload(DecisionStrategy.candidates).selectinload(StrategyCandidate.requirements),
                selectinload(DecisionStrategy.candidates).selectinload(StrategyCandidate.metadata),
                selectinload(DecisionStrategy.candidates).selectinload(StrategyCandidate.evaluations),
                selectinload(DecisionStrategy.rankings),
                selectinload(DecisionStrategy.scores),
                selectinload(DecisionStrategy.reasons),
                selectinload(DecisionStrategy.constraints),
                selectinload(DecisionStrategy.requirements),
                selectinload(DecisionStrategy.metadata_rows),
                selectinload(DecisionStrategy.evaluations),
                selectinload(DecisionStrategy.history),
                selectinload(DecisionStrategy.versions),
            )
        )
        result = await self.db.execute(stmt)
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