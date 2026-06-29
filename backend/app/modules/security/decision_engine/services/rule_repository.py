from __future__ import annotations
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..models.rules import DecisionRule
from .rule_interfaces import IRuleRepository

class RuleRepository(IRuleRepository):
    """
    SQLAlchemy implementation of the Rule Repository.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_rules(self, tenant_id: str) -> List[DecisionRule]:
        """
        Retrieves all active rules for a specific tenant.

        Sprint 2 R17: eagerly load ``conditions``, ``actions`` and ``versions``
        so callers (engine + API routes) can iterate them without triggering
        lazy loads on a detached async session.
        """
        query = (
            select(DecisionRule)
            .where(
                DecisionRule.tenant_id == tenant_id,
                DecisionRule.is_active == True,
            )
            .options(
                selectinload(DecisionRule.conditions),
                selectinload(DecisionRule.actions),
                selectinload(DecisionRule.versions),
                selectinload(DecisionRule.dependencies),
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_rule_by_id(self, rule_id: str, tenant_id: str) -> Optional[DecisionRule]:
        """
        Retrieves a specific rule by ID.

        Sprint 2 R17: eagerly load child collections.
        """
        query = (
            select(DecisionRule)
            .where(DecisionRule.id == rule_id, DecisionRule.tenant_id == tenant_id)
            .options(
                selectinload(DecisionRule.conditions),
                selectinload(DecisionRule.actions),
                selectinload(DecisionRule.versions),
                selectinload(DecisionRule.dependencies),
                selectinload(DecisionRule.executions),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
