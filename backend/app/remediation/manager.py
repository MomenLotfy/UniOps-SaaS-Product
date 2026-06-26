from __future__ import annotations
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.remediation.interfaces.base import RemediationContext, ExecutionPlan
from app.remediation.registry.registry import CapabilityRegistry
from app.remediation.engine.decision_engine import RemediationDecisionEngine
from app.remediation.engine.pipeline import ExecutionPipeline
from app.utils.logger import logger

class RemediationManager:
    """
    The primary facade for the Remediation Engine.
    Coordinates the Decision Engine and Execution Pipeline.
    """
    def __init__(self, db: AsyncSession, registry: CapabilityRegistry):
        self.db = db
        self.registry = registry
        self.decision_engine = RemediationDecisionEngine(registry)
        self.pipeline = ExecutionPipeline(registry, db)

    async def propose_remediation(self, context: RemediationContext) -> Optional[ExecutionPlan]:
        """
        Analyzes a finding and proposes a remediation plan without executing it.
        """
        return await self.decision_engine.decide_remediation(context)

    async def run_remediation(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """
        Executes a previously proposed remediation plan.
        """
        return await self.pipeline.execute_plan(context, plan)

    async def full_remediation_cycle(self, context: RemediationContext) -> Any:
        """
        Automatic end-to-end cycle: Propose -> Execute.
        """
        plan = await self.propose_remediation(context)
        if not plan:
            return {"status": "failed", "error": "No suitable remediation plan could be generated."}

        return await self.run_remediation(context, plan)
