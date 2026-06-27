from __future__ import annotations
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.base import BaseService
from ..models.decision import Decision
from ..services.decision_manager import DecisionManager
from ..services.decision_pipeline import DecisionPipeline
from ..services.context_builder import DecisionContextBuilder
from ..services.decision_validator import DecisionValidator
from ..services.decision_engine import DecisionEngine

class DecisionService(BaseService):
    """
    API Facade for the Decision Engine.
    """
    async def list_decisions(self, tenant_id: str, status: Optional[str] = None) -> List[Decision]:
        query = select(Decision).where(Decision.tenant_id == tenant_id)
        if status:
            query = query.where(Decision.status == status)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_decision_detail(self, tenant_id: str, decision_id: str) -> Optional[Decision]:
        result = await self.db.execute(
            select(Decision).where(Decision.id == decision_id, Decision.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def request_decision(self, tenant_id: str, finding_id: str, correlation_id: str) -> Decision:
        """
        Internal method to trigger the decision pipeline.
        """
        manager = DecisionManager(self.db)
        builder = DecisionContextBuilder(self.db)
        validator = DecisionValidator(self.db)
        engine = DecisionEngine()
        pipeline = DecisionPipeline(self.db, builder, validator, engine, manager)

        return await pipeline.execute(tenant_id, finding_id, correlation_id)
