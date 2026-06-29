"""
Decision Strategy Statistics Service.

Maintains per-strategy-type counters + average evaluation durations in
the `StrategyStatistics` table.  Called by the engine after each
successful evaluation.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import StrategyState, StrategyType
from ..models.strategy import StrategyStatistics


class DecisionStrategyStatisticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_evaluation(
        self,
        tenant_id: str,
        strategy_type: StrategyType,
        duration_ms: int,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Upsert the per-(tenant, strategy_type, state) statistics row,
        updating the running average duration.

        R27: ``state`` and ``correlation_id`` are NOT NULL on every
        DecisionBase row.  Statistics rows default to the SELECTED
        state — they count evaluations that produced a winning
        strategy.  ``correlation_id`` falls back to a deterministic
        placeholder when the caller cannot supply one.
        """
        result = await self.db.execute(
            select(StrategyStatistics).where(
                StrategyStatistics.tenant_id == tenant_id,
                StrategyStatistics.strategy_type == strategy_type,
                StrategyStatistics.state == StrategyState.SELECTED,
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = StrategyStatistics(
                tenant_id=tenant_id,
                strategy_type=strategy_type,
                state=StrategyState.SELECTED,
                correlation_id=correlation_id or f"strategy-stats:{tenant_id}:{strategy_type.value}",
                count=1,
                avg_duration_ms=float(duration_ms),
            )
            self.db.add(row)
        else:
            new_count = row.count + 1
            row.avg_duration_ms = (
                (row.avg_duration_ms * row.count) + float(duration_ms)
            ) / new_count
            row.count = new_count

        await self.db.flush()

    async def record_rejection(
        self,
        tenant_id: str,
        strategy_type: StrategyType,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Increment rejection counter without touching duration.
        """
        result = await self.db.execute(
            select(StrategyStatistics).where(
                StrategyStatistics.tenant_id == tenant_id,
                StrategyStatistics.strategy_type == strategy_type,
                StrategyStatistics.state == StrategyState.REJECTED,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = StrategyStatistics(
                tenant_id=tenant_id,
                strategy_type=strategy_type,
                state=StrategyState.REJECTED,
                correlation_id=correlation_id or f"strategy-stats:{tenant_id}:{strategy_type.value}:REJECTED",
                count=0,
                rejection_count=1,
                avg_duration_ms=0.0,
            )
            self.db.add(row)
        else:
            row.rejection_count = (row.rejection_count or 0) + 1
        await self.db.flush()