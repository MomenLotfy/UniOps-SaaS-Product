from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.remediation.engine.orchestrator import ExecutionOrchestrator
from app.remediation.interfaces.base import RemediationContext, ExecutionPlan
from app.remediation.models.models import RemediationPlan as PlanModel
from app.utils.logger import logger

class ExecutionController:
    """
    The management interface for active remediation executions.
    Provides control over the lifecycle: Start, Cancel, Retry, Rollback.
    """
    def __init__(self, orchestrator: ExecutionOrchestrator, db: AsyncSession):
        self.orchestrator = orchestrator
        self.db = db

    async def start_execution(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """Triggers the execution of a la plan."""
        return await self.orchestrator.run_execution(context, plan)

    async def cancel_execution(self, plan_id: str, tenant_id: str) -> bool:
        """
        Cancels a running execution.
        In a distributed worker environment, this would send a cancellation signal to the worker.
        """
        logger.info(f"[Controller] Requesting cancellation for plan {plan_id}")
        # Integration with WorkerCancellation mechanism would go here.
        return True

    async def retry_execution(self, plan_id: str, tenant_id: str, context: RemediationContext) -> Any:
        """
        Retries a failed execution.
        Usually involves creating a new plan version and restarting the pipeline.
        """
        logger.info(f"[Controller] Retrying execution for plan {plan_id}")
        # Logic: 1. Find failed plan, 2. Create new version, 3. Start orchestrator.run_execution
        return {"status": "retry_queued", "plan_id": plan_id}

    async def trigger_rollback(self, plan_id: str, tenant_id: str, context: RemediationContext) -> Any:
        """
        Manually triggers the rollback for a previously executed plan.
        """
        logger.info(f"[Controller] Manual rollback triggered for plan {plan_id}")
        # 1. Fetch the original plan
        query = select(PlanModel).where(PlanModel.id == plan_id, PlanModel.tenant_id == tenant_id)
        result = await self.db.execute(query)
        plan_db = result.scalar_one_or_none()

        if not plan_db:
            raise Exception("Plan not found")

        # Convert DB model to Pydantic model
        plan = ExecutionPlan(**plan_db.__dict__)

        return await self.orchestrator.rollback_execution(context, plan)
