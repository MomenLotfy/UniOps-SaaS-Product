"""
Decision Strategy Manager.

Wraps `DecisionStrategyLifecycleManager` and exposes the public
state-machine surface used by the engine + service layer.

Mirrors `DecisionManager` in the sibling decision_engine module.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import StrategyState
from ..models.strategy import DecisionStrategy
from .strategy_lifecycle_manager import DecisionStrategyLifecycleManager


class DecisionStrategyManager:
    """
    Public API for state transitions and versioning.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.lifecycle = DecisionStrategyLifecycleManager(db)

    # ── State Transitions ──────────────────────────────────────────────
    async def transition(
        self,
        strategy_id: str,
        to_state: StrategyState,
        changed_by: str = "system",
        reason: Optional[str] = None,
    ) -> DecisionStrategy:
        return await self.lifecycle.transition_to(
            strategy_id=strategy_id,
            to_state=to_state,
            changed_by=changed_by,
            reason=reason,
        )

    async def approve(self, strategy_id: str, changed_by: str = "system") -> DecisionStrategy:
        """Move SELECTED → APPROVED."""
        return await self.lifecycle.transition_to(
            strategy_id=strategy_id,
            to_state=StrategyState.APPROVED,
            changed_by=changed_by,
            reason="Approved for execution",
        )

    async def reject(self, strategy_id: str, reason: str, changed_by: str = "system") -> DecisionStrategy:
        """Move SELECTED/APPROVED → REJECTED."""
        return await self.lifecycle.transition_to(
            strategy_id=strategy_id,
            to_state=StrategyState.REJECTED,
            changed_by=changed_by,
            reason=reason,
        )

    async def archive(self, strategy_id: str, reason: Optional[str] = None) -> DecisionStrategy:
        """Terminal: any non-archived state → ARCHIVED."""
        return await self.lifecycle.transition_to(
            strategy_id=strategy_id,
            to_state=StrategyState.ARCHIVED,
            changed_by="system",
            reason=reason or "Archived",
        )

    async def start_execution(self, strategy_id: str) -> DecisionStrategy:
        """APPROVED → EXECUTING."""
        return await self.lifecycle.transition_to(
            strategy_id=strategy_id,
            to_state=StrategyState.EXECUTING,
            changed_by="system",
            reason="Execution started",
        )

    async def mark_completed(self, strategy_id: str) -> DecisionStrategy:
        """EXECUTING → COMPLETED."""
        return await self.lifecycle.transition_to(
            strategy_id=strategy_id,
            to_state=StrategyState.COMPLETED,
            changed_by="system",
            reason="Execution completed",
        )

    async def mark_failed(self, strategy_id: str, reason: str) -> DecisionStrategy:
        """EXECUTING → FAILED."""
        return await self.lifecycle.transition_to(
            strategy_id=strategy_id,
            to_state=StrategyState.FAILED,
            changed_by="system",
            reason=reason,
        )

    # ── Versioning ─────────────────────────────────────────────────────
    async def snapshot(self, strategy_id: str, change_summary: Optional[str] = None):
        return await self.lifecycle.create_version_snapshot(strategy_id, change_summary)

    async def rollback(self, strategy_id: str, version_number: int) -> DecisionStrategy:
        return await self.lifecycle.rollback_to_version(strategy_id, version_number)