from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
from pydantic import BaseModel
from app.remediation.interfaces.base import RemediationContext, ExecutionPlan
from app.utils.logger import logger

class PipelineStage(str, Enum):
    """The deterministic stages of a remediation execution pipeline."""
    PRE_VALIDATION = "pre_validation"
    POLICY_VALIDATION = "policy_validation"
    CAPABILITY_PREP = "capability_prep"
    EXECUTION_PREP = "execution_prep"
    EXECUTION = "execution"
    POST_EXECUTION = "post_execution"
    VERIFICATION = "verification"
    COMPLETION = "completion"
    ROLLBACK = "rollback"

class StageResult(BaseModel):
    """The outcome of a specific pipeline stage."""
    stage: PipelineStage
    status: str # success | failed | skipped
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0

class ExecutionPipeline:
    """
    Orchestrates the sequential execution of remediation stages.
    This class does not contain business logic; it coordinates the call
    to the appropriate plugins and validators for each stage.
    """
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        self.stages = [
            PipelineStage.PRE_VALIDATION,
            PipelineStage.POLICY_VALIDATION,
            PipelineStage.CAPABILITY_PREP,
            PipelineStage.EXECUTION_PREP,
            PipelineStage.EXECUTION,
            PipelineStage.POST_EXECUTION,
            PipelineStage.VERIFICATION,
            PipelineStage.COMPLETION
        ]

    async def run(self, context: RemediationContext, plan: ExecutionPlan) -> List[StageResult]:
        """
        Executes the pipeline stages in order.
        """
        results = []

        try:
            for stage in self.stages:
                result = await self._execute_stage(stage, context, plan)
                results.append(result)

                if result.status == "failed":
                    logger.error(f"[Pipeline] Stage {stage} failed. Initiating rollback.")
                    await self._handle_rollback(context, plan)
                    break

            return results

        except Exception as e:
            logger.exception(f"[Pipeline] Critical failure during pipeline execution: {e}")
            await self._handle_rollback(context, plan)
            return results

    async def _execute_stage(self, stage: PipelineStage, context: RemediationContext, plan: ExecutionPlan) -> StageResult:
        """
        Routes the execution to the specific handler for the stage.
        """
        import time
        start = time.time()

        try:
            # Routing logic to orchestrator methods
            if stage == PipelineStage.PRE_VALIDATION:
                success = await self.orchestrator.validate_pre_execution(context, plan)
                status = "success" if success else "failed"
                output = "Pre-validation passed" if success else "Pre-validation failed"

            elif stage == PipelineStage.POLICY_VALIDATION:
                success = await self.orchestrator.validate_policies(context, plan)
                status = "success" if success else "failed"
                output = "Policies compliant" if success else "Policy violation"

            elif stage == PipelineStage.CAPABILITY_PREP:
                # Resolve and prepare the plugin/strategy
                output = await self.orchestrator.prepare_capability(context, plan)
                status = "success" if output else "failed"

            elif stage == PipelineStage.EXECUTION_PREP:
                # Final check and resource locking
                output = await self.orchestrator.prepare_execution(context, plan)
                status = "success" if output else "failed"

            elif stage == PipelineStage.EXECUTION:
                # Call the actual strategy execute()
                output = await self.orchestrator.execute_strategy(context, plan)
                status = "success" if output else "failed"

            elif stage == PipelineStage.POST_EXECUTION:
                output = await self.orchestrator.post_execute(context, plan)
                status = "success" if output else "failed"

            elif stage == PipelineStage.VERIFICATION:
                output = await self.orchestrator.verify_remediation(context, plan)
                status = "success" if output else "failed"

            elif stage == PipelineStage.COMPLETION:
                output = await self.orchestrator.finalize_execution(context, plan)
                status = "success" if output else "failed"

            else:
                status = "skipped"
                output = None

            return StageResult(
                stage=stage,
                status=status,
                output=output,
                duration_ms=(time.time() - start) * 1000
            )

        except Exception as e:
            logger.error(f"[Pipeline] Exception in stage {stage}: {e}")
            return StageResult(stage=stage, status="failed", error=str(e), duration_ms=(time.time() - start) * 1000)

    async def _handle_rollback(self, context: RemediationContext, plan: ExecutionPlan):
        """
        Coordinates the rollback process across the strategy and state machine.
        """
        logger.info(f"[Pipeline] Triggering rollback for plan {plan.plan_id}")
        try:
            # Call orchestrator to perform the strategy rollback
            await self.orchestrator.rollback_execution(context, plan)
        except Exception as e:
            logger.exception(f"[Pipeline] Rollback failed: {e}")
