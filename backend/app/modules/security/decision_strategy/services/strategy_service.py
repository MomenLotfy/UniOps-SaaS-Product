"""
Decision Strategy Service — read-only API facade.

Mirrors `DecisionService` in the sibling decision_engine module.
Only read paths + lifecycle transitions are exposed.  No business
logic here — delegate to the engine, repository and manager.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import StrategyState, StrategyType
from ..models.strategy import DecisionStrategy, StrategyHistory, StrategyVersion
from .strategy_interfaces import StrategyEvaluationResult
from .strategy_manager import DecisionStrategyManager
from .strategy_repository import DecisionStrategyRepository


class DecisionStrategyService:
    """
    Read-only facade.  Lifecycle transitions are intentionally
    available — the manager wraps the lifecycle manager which validates
    transitions.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = DecisionStrategyRepository(db)
        self.manager = DecisionStrategyManager(db)

    # ── Reads ──────────────────────────────────────────────────────────
    async def list_strategies(
        self,
        tenant_id: str,
        state: Optional[StrategyState] = None,
        strategy_type: Optional[StrategyType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DecisionStrategy]:
        return await self.repository.list_for_tenant(
            tenant_id=tenant_id,
            state=state,
            strategy_type=strategy_type,
            limit=limit,
            offset=offset,
        )

    async def get_strategy(self, strategy_id: str) -> Optional[DecisionStrategy]:
        return await self.repository.get_by_id(strategy_id)

    async def list_history(self, strategy_id: str) -> List[StrategyHistory]:
        return await self.repository.list_history(strategy_id)

    async def list_versions(self, strategy_id: str) -> List[StrategyVersion]:
        return await self.repository.list_versions(strategy_id)

    async def get_statistics(self, tenant_id: str) -> dict:
        return await self.repository.get_statistics(tenant_id)

    # ── Lifecycle (kept here for completeness) ────────────────────────
    async def transition(
        self,
        strategy_id: str,
        to_state: StrategyState,
        changed_by: str = "system",
        reason: Optional[str] = None,
    ) -> DecisionStrategy:
        return await self.manager.transition(
            strategy_id=strategy_id,
            to_state=to_state,
            changed_by=changed_by,
            reason=reason,
        )

    async def archive(
        self,
        strategy_id: str,
        reason: Optional[str] = None,
    ) -> DecisionStrategy:
        return await self.manager.archive(strategy_id, reason)

    async def snapshot(
        self,
        strategy_id: str,
        change_summary: Optional[str] = None,
    ) -> StrategyVersion:
        return await self.manager.snapshot(strategy_id, change_summary)