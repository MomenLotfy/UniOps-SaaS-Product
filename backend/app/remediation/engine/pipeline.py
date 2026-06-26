from __future__ import annotations
from typing import Any, Optional
import uuid
from datetime import datetime, timezone

from app.remediation.interfaces.base import RemediationContext, ExecutionPlan, IRemediationValidator
from app.remediation.registry.registry import CapabilityRegistry
from app.remediation.models.models import RemediationExecutionHistory
from app.utils.logger import logger

class ExecutionPipeline:
    """
    Orchestrates the end-to-end execution of a remediation plan.
    Handles Validation -> Execution -> Telemetry -> Recording.
    """
    def __init__(self, registry: CapabilityRegistry, db_session, validator: Optional[IRemediationValidator] = None):
        self.registry = registry
        self.db = db_session
        self.validator = validator

    async def execute_plan(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """
        Executes the remediation plan and records the outcome.
        """
        logger.info(f"[Pipeline] Starting execution for plan {plan.plan_id}")

        # 1. Validation Phase
        # Ensure the plan is still applicable and safe to execute.
        if self.validator:
            is_valid = await self.validator.validate(plan, context)
            if not is_valid:
                logger.error(f"[Pipeline] Plan {plan.plan_id} failed pre-execution validation")
                return {"status": "failed", "error": "Pre-execution validation failed"}

        # 2. Strategy Retrieval
        # Find the plugin responsible for the capability and get the specific strategy.
        capability_handler = self.registry.get_capability(plan.capability_id)
        if not capability_handler:
            logger.error(f"[Pipeline] No handler found for capability {plan.capability_id}")
            return {"status": "failed", "error": f"Capability {plan.capability_id} not available"}

        try:
            strategy = await capability_handler.get_strategy(plan.strategy_id)
        except Exception as e:
            logger.error(f"[Pipeline] Error retrieving strategy {plan.strategy_id}: {e}")
            return {"status": "failed", "error": str(e)}

        if not strategy:
            logger.error(f"[Pipeline] Strategy {plan.strategy_id} not found in plugin")
            return {"status": "failed", "error": "Remediation strategy not found"}

        # 3. Execution and recording
        execution_id = str(uuid.uuid4())
        history_entry = RemediationExecutionHistory(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            tenant_id=context.tenant_id,
            start_time=datetime.now(timezone.utc),
            status="started"
        )
        self.db.add(history_entry)
        await self.db.commit()

        try:
            # The core execution logic resides in the strategy plugin.
            result = await strategy.execute(context, plan)

            # Update history on success
            history_entry.status = "success"
            history_entry.end_time = datetime.now(timezone.utc)
            history_entry.result_metadata = {"output": result}

            # Update the plan status to completed.
            plan.status = "completed"

        except Exception as e:
            logger.exception(f"[Pipeline] Critical error during execution of plan {plan.plan_id}")
            history_entry.status = "failed"
            history_entry.error_message = str(e)
            history_entry.end_time = datetime.now(timezone.utc)
            plan.status = "failed"
            return {"status": "failed", "error": str(e)}
        finally:
            # Final commit for the execution record.
            await self.db.commit()

        logger.info(f"[Pipeline] Successfully executed plan {plan.plan_id} (ID: {execution_id})")
        return {"status": "success", "execution_id": execution_id, "result": result}
