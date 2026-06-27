"""
Decision Strategy Lifecycle Manager.

Handles state transitions + versioning + audit.

Mirrors the role of `DecisionManager` in the sibling decision_engine
module, but for the strategy engine.  Pure DB writes — no business
logic.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import VALID_STRATEGY_TRANSITIONS, StrategyState
from ..models.strategy import DecisionStrategy, StrategyHistory, StrategyVersion
from .strategy_serializer import serialize_strategy_snapshot


class DecisionStrategyLifecycleManager:
    """
    Owns lifecycle transitions and version snapshots for DecisionStrategy.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Transitions ─────────────────────────────────────────────────────
    async def transition_to(
        self,
        strategy_id: str,
        to_state: StrategyState,
        changed_by: str = "system",
        reason: Optional[str] = None,
    ) -> DecisionStrategy:
        """
        Atomically:
          - load current row
          - validate transition via VALID_STRATEGY_TRANSITIONS
          - update status
          - append a StrategyHistory row
        """
        result = await self.db.execute(
            select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
        )
        strategy = result.scalar_one_or_none()
        if strategy is None:
            raise ValueError(f"DecisionStrategy {strategy_id} not found")

        current = strategy.state
        allowed = VALID_STRATEGY_TRANSITIONS.get(current, [])
        if to_state not in allowed:
            raise ValueError(
                f"Invalid strategy transition: {current} -> {to_state}"
            )

        strategy.state = to_state

        hist = StrategyHistory(
            tenant_id=strategy.tenant_id,
            strategy_id=strategy_id,
            from_state=current,
            to_state=to_state,
            changed_by=changed_by,
            change_reason=reason,
            correlation_id=strategy.correlation_id,
            trace_id=strategy.trace_id,
        )
        self.db.add(hist)
        await self.db.flush()
        return strategy

    # ── Versioning ──────────────────────────────────────────────────────
    async def create_version_snapshot(self, strategy_id: str,
                                      change_summary: Optional[str] = None) -> StrategyVersion:
        """
        Captures the current state of a DecisionStrategy into a
        StrategyVersion row.  Increments version_number monotonically.
        """
        result = await self.db.execute(
            select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
        )
        strategy = result.scalar_one_or_none()
        if strategy is None:
            raise ValueError(f"DecisionStrategy {strategy_id} not found")

        last = await self.db.execute(
            select(StrategyVersion.version_number)
            .where(StrategyVersion.strategy_id == strategy_id)
            .order_by(desc(StrategyVersion.version_number))
        )
        prev = last.scalar_one_or_none()
        next_version = (prev + 1) if prev else 1

        snapshot = serialize_strategy_snapshot(strategy)
        version = StrategyVersion(
            tenant_id=strategy.tenant_id,
            strategy_id=strategy_id,
            version_number=next_version,
            snapshot=snapshot,
            change_summary=change_summary,
            correlation_id=strategy.correlation_id,
            trace_id=strategy.trace_id,
        )
        self.db.add(version)
        await self.db.flush()
        return version

    async def rollback_to_version(self, strategy_id: str, version_number: int) -> DecisionStrategy:
        """
        Restore a strategy's mutable fields from a previous version
        snapshot.  Constraints, requirements and reasons are NOT
        reverted (they have their own history tables).
        """
        result = await self.db.execute(
            select(StrategyVersion).where(
                StrategyVersion.strategy_id == strategy_id,
                StrategyVersion.version_number == version_number,
            )
        )
        version = result.scalar_one_or_none()
        if version is None:
            raise ValueError(
                f"StrategyVersion {version_number} for strategy {strategy_id} not found"
            )

        snap = version.snapshot

        strat_res = await self.db.execute(
            select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
        )
        strategy = strat_res.scalar_one_or_none()
        if strategy is None:
            raise ValueError(f"DecisionStrategy {strategy_id} not found")

        # Restore mutable fields only
        strategy.priority    = snap.get("priority", strategy.priority)
        strategy.confidence  = snap.get("confidence", strategy.confidence)
        strategy.risk_score  = snap.get("risk_score", strategy.risk_score)
        strategy.feasibility_score = snap.get("feasibility_score", strategy.feasibility_score)
        strategy.composite_score   = snap.get("composite_score", strategy.composite_score)
        strategy.business_justification  = snap.get("business_justification")
        strategy.technical_justification = snap.get("technical_justification")
        strategy.selection_reason       = snap.get("selection_reason")
        strategy.expected_downtime_min  = snap.get("expected_downtime_min")
        strategy.requires_human_approval = snap.get("requires_human_approval", False)
        strategy.is_reversible          = snap.get("is_reversible", True)

        # Record history
        hist = StrategyHistory(
            tenant_id=strategy.tenant_id,
            strategy_id=strategy_id,
            from_state=strategy.state,
            to_state=strategy.state,  # no change — pure rollback audit
            changed_by="system",
            change_reason=f"Rollback to v{version_number}",
            correlation_id=strategy.correlation_id,
            trace_id=strategy.trace_id,
        )
        self.db.add(hist)
        await self.db.flush()
        return strategy