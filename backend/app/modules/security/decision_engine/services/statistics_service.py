from __future__ import annotations
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.statistics import DecisionStatistics
from ..models.policy import PolicyStatistics
from ..constants import DecisionState

class StatisticsService:
    """
    Handles aggregation and persistence of metrics for the Decision Engine.
    Tracks both global pipeline performance and granular policy effectiveness.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_decision_stats(
        self,
        tenant_id: str,
        state: DecisionState,
        duration_ms: float,
        correlation_id: Optional[str] = None,
    ):
        """
        Updates the global decision statistics for the tenant.

        ``correlation_id`` is required by the ``DecisionBase`` mixin but
        aggregated statistics rows are tenant-level, not request-level.
        When the caller cannot supply one, fall back to a deterministic
        placeholder so the row still satisfies the NOT NULL constraint.
        """
        effective_corr = correlation_id or f"decision-stats:{tenant_id}:{state.value}"
        # Upsert logic for DecisionStatistics
        stmt = select(DecisionStatistics).where(
            DecisionStatistics.tenant_id == tenant_id,
            DecisionStatistics.state == state
        )
        result = await self.db.execute(stmt)
        stats = result.scalar_one_or_none()

        if stats:
            # Update moving average: avg = (old_avg * old_count + new_val) / (old_count + 1)
            new_count = stats.count + 1
            stats.avg_duration_ms = ((stats.avg_duration_ms * stats.count) + duration_ms) / new_count
            stats.count = new_count
        else:
            stats = DecisionStatistics(
                tenant_id=tenant_id,
                correlation_id=effective_corr,
                state=state,
                count=1,
                avg_duration_ms=duration_ms
            )
            self.db.add(stats)

    async def record_policy_stats(
        self,
        policy_id: str,
        duration_ms: float,
        was_overridden: bool,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """
        Updates granular metrics for a specific policy.

        ``tenant_id`` and ``correlation_id`` are required by the
        ``DecisionBase`` mixin (correlation_id is ``NOT NULL`` in the
        schema).  When the caller cannot supply them (legacy callers
        before R27) they fall back to ``policy_id``-derived defaults
        so the row still satisfies the NOT NULL constraint.
        """
        effective_tenant = tenant_id or f"policy:{policy_id}"
        effective_corr = correlation_id or f"policy-stats:{policy_id}"
        stmt = select(PolicyStatistics).where(PolicyStatistics.policy_id == policy_id)
        result = await self.db.execute(stmt)
        stats = result.scalar_one_or_none()

        if stats:
            stats.match_count += 1
            if was_overridden:
                stats.override_count += 1

            # Update moving average for evaluation time
            new_count = stats.match_count
            stats.avg_eval_time_ms = ((stats.avg_eval_time_ms * (new_count - 1)) + duration_ms) / new_count
        else:
            stats = PolicyStatistics(
                tenant_id=effective_tenant,
                correlation_id=effective_corr,
                policy_id=policy_id,
                match_count=1,
                override_count=1 if was_overridden else 0,
                avg_eval_time_ms=duration_ms,
            )
            self.db.add(stats)

    async def get_tenant_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """
        Retrieves overall decision metrics for a tenant.
        """
        stmt = select(DecisionStatistics).where(DecisionStatistics.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        stats_list = result.scalars().all()

        return {
            "total_decisions": sum(s.count for s in stats_list),
            "by_state": {s.state: s.count for s in stats_list},
            "avg_durations": {s.state: s.avg_duration_ms for s in stats_list}
        }

    async def get_policy_metrics(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves granular metrics for a specific policy.
        """
        stmt = select(PolicyStatistics).where(PolicyStatistics.policy_id == policy_id)
        result = await self.db.execute(stmt)
        stats = result.scalar_one_or_none()

        if not stats:
            return None

        return {
            "match_count": stats.match_count,
            "override_count": stats.override_count,
            "override_rate": (stats.override_count / stats.match_count) if stats.match_count > 0 else 0,
            "avg_eval_time_ms": stats.avg_eval_time_ms
        }
