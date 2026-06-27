from __future__ import annotations
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
        """
        query = select(DecisionRule).where(
            DecisionRule.tenant_id == tenant_id,
            DecisionRule.is_active == True
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_rule_by_id(self, rule_id: str, tenant_id: str) -> Optional[DecisionRule]:
        """
        Retrieves a specific rule by ID.
        """
        result = await self.db.execute(
            select(DecisionRule).where(DecisionRule.id == rule_id, DecisionRule.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()
