from __future__ import annotations
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.remediation.interfaces.base import RemediationContext, ExecutionPlan
from app.remediation.registry.registry import CapabilityRegistry
from app.remediation.engine.decision_engine import RemediationDecisionEngine
from app.remediation.engine.ai_support import DecisionSupportAI
from app.remediation.engine.pipeline import ExecutionPipeline
from app.remediation.engine.quotas import ExecutionQuotas
from app.remediation.engine.recovery import RecoveryManager
from app.services.copilot_service import CopilotService
from app.utils.logger import logger

class RemediationManager:
    """
    The primary facade for the Remediation Engine.
    Coordinates the Decision Engine, Execution Pipeline, and Runtime Hardening (Quotas, Recovery).
    """
    def __init__(self, db: AsyncSession, registry: CapabilityRegistry, copilot_service: Optional[CopilotService] = None):
        self.db = db
        self.registry = registry

        # Setup AI support if service is provided
        ai_support = None
        if copilot_service:
            ai_support = DecisionSupportAI(copilot_service)

        self.decision_engine = RemediationDecisionEngine(registry, ai_support=ai_support)
        self.pipeline = ExecutionPipeline(registry, db)
        self.quotas = ExecutionQuotas(db)
        self.recovery = RecoveryManager(db)

    async def propose_remediation(self, context: RemediationContext) -> Optional[ExecutionPlan]:
        """
        Analyzes a finding and proposes a remediation plan without executing it.
        """
        return await self.decision_engine.create_execution_plan(context)

    async def run_remediation(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """
        Executes a previously proposed remediation plan after validating quotas.
        """
        # 1. Quota Check
        if not await self.quotas.check_quota(context.tenant_id):
            logger.warning(f"[RemediationManager] Execution quota exceeded for tenant {context.tenant_id}")
            return {"status": "failed", "error": "Concurrent execution quota exceeded. Please try again later."}

        return await self.pipeline.execute_plan(context, plan)

    async def perform_recovery_scan(self, tenant_id: Optional[str] = None) -> Any:
        """
        Triggers a scan for stuck executions and attempts recovery.
        """
        return await self.recovery.scan_and_recover_stuck_executions(tenant_id)

    async def full_remediation_cycle(self, context: RemediationContext) -> Any:
        """
        Automatic end-to-end cycle: Propose -> Execute.
        """
        plan = await self.propose_remediation(context)
        if not plan:
            return {"status": "failed", "error": "No suitable remediation plan could be generated."}

        return await self.run_remediation(context, plan)
