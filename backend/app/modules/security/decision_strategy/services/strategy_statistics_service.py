"""
Decision Strategy Statistics Service.

Maintains per-strategy-type counters + average evaluation durations in
the `StrategyStatistics` table.  Called by the engine after each
successful evaluation.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import StrategyType
from ..models.strategy import StrategyStatistics


class DecisionStrategyStatisticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_evaluation(
        self,
        tenant_id: str,
        strategy_type: StrategyType,
        duration_ms: int,
    ) -> None:
        """
        Upsert the per-(tenant, strategy_type) statistics row, updating
        the running average duration.
        """
        result = await self.db.execute(
            select(StrategyStatistics).where(
                StrategyStatistics.tenant_id == tenant_id,
                StrategyStatistics.strategy_type == strategy_type,
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = StrategyStatistics(
                tenant_id=tenant_id,
                strategy_type=strategy_type,
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

    async def record_rejection(self, tenant_id: str, strategy_type: StrategyType) -> None:
        """
        Increment rejection counter without touching duration.
        """
        result = await self.db.execute(
            select(StrategyStatistics).where(
                StrategyStatistics.tenant_id == tenant_id,
                StrategyStatistics.strategy_type == strategy_type,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = StrategyStatistics(
                tenant_id=tenant_id,
                strategy_type=strategy_type,
                count=0,
                avg_duration_ms=0.0,
            )
            self.db.add(row)
        row.rejection_count = (row.rejection_count or 0) + 1
        await self.db.flush()