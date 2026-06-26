from __future__ import annotations
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime, timezone

from app.remediation.interfaces.base import RemediationContext, ExecutionPlan, IRemediationStrategy
from app.remediation.registry.registry import CapabilityRegistry
from app.remediation.engine.locks import LockManager, InMemoryLockProvider
from app.remediation.engine.pipeline import ExecutionPipeline, StageResult
from app.remediation.events.bus import event_bus
from app.remediation.events.messages import RemediationMessage, RemediationEventType
from app.remediation.lifecycle.state import RemediationState, StateMachine
from app.remediation.models.models import RemediationPlan as PlanModel, RemediationStateHistory
from app.utils.logger import logger

class ExecutionOrchestrator:
    """
    The central coordinator for remediation execution.
    Implements the high-level flow: Validation -> Preparation -> Execution -> Verification.
    """
    def __init__(self, registry: CapabilityRegistry, db_session, lock_manager: Optional[LockManager] = None):
        self.registry = registry
        self.db = db_session
        self.lock_manager = lock_manager or LockManager(InMemoryLockProvider())
        self.pipeline = ExecutionPipeline(self)

    async def run_execution(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """
        The entry point for executing a remediation plan.
        """
        # 1. Traceability: Emit start event
        await self._emit_event(context, plan, RemediationEventType.EXECUTION_STARTED)

        # 2. Acquire Locks (Atomic)
        locks = []
        try:
            locks = await self.lock_manager.acquire_execution_locks(
                context.tenant_id, context.repo_id, context.finding_id
            )
        except Exception as e:
            logger.error(f"[Orchestrator] Failed to acquire locks: {e}")
            return {"status": "failed", "error": f"Resource lock error: {str(e)}"}

        try:
            # 3. Run the Pipeline
            results = await self.pipeline.run(context, plan)

            # Determine final outcome
            final_status = "success" if all(r.status == "success" for r in results) else "failed"

            # 4. Update Plan State
            target_state = RemediationState.COMPLETED if final_status == "success" else RemediationState.FAILED
            await self._transition_state(plan, target_state, f"Pipeline finished with status: {final_status}")

            await self._emit_event(
                context, plan,
                RemediationEventType.EXECUTION_COMPLETED if final_status == "success" else RemediationEventType.EXECUTION_FAILED
            )

            return {"status": final_status, "pipeline_results": [r.dict() for r in results]}

        except Exception as e:
            logger.exception(f"[Orchestrator] Unhandled exception during orchestration: {e}")
            await self._transition_state(plan, RemediationState.FAILED, str(e))
            return {"status": "failed", "error": str(e)}
        finally:
            # 5. Always release locks
            await self.lock_manager.release_execution_locks(locks)

    # ── Pipeline Stage Handlers ─────────────────────────────────────────────────────

    async def validate_pre_execution(self, context: RemediationContext, plan: ExecutionPlan) -> bool:
        """Stage: PRE_VALIDATION - Basic health and consistency checks."""
        logger.info(f"[Orchestrator] Running Pre-Validation for plan {plan.plan_id}")
        return True # Logic for basic health check

    async def validate_policies(self, context: RemediationContext, plan: ExecutionPlan) -> bool:
        """Stage: POLICY_VALIDATION - Evaluate execution against tenant policies."""
        logger.info(f"[Orchestrator] Validating policies for plan {plan.plan_id}")
        # Integration with Policy Engine would go here
        return True

    async def prepare_capability(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """Stage: CAPABILITY_PREP - Load the plugin and validate its current health."""
        logger.info(f"[Orchestrator] Preparing capability {plan.capability_id}")
        plugin = self.registry.get_capability(plan.capability_id)
        if not plugin:
            raise Exception(f"Capability {plan.capability_id} not found")
        return {"plugin_id": plugin.plugin_id, "status": "ready"}

    async def prepare_execution(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """Stage: EXECUTION_PREP - Final setup, resource checks, and input verification."""
        logger.info(f"[Orchestrator] Final preparation for plan {plan.plan_id}")
        return {"ready": True}

    async def execute_strategy(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """Stage: EXECUTION - Invoke the actual remediation strategy."""
        logger.info(f"[Orchestrator] Executing strategy {plan.strategy_id}")

        plugin = self.registry.get_capability(plan.capability_id)
        strategy = await plugin.get_strategy(plan.strategy_id)

        if not strategy:
            raise Exception(f"Strategy {plan.strategy_id} not found in plugin {plugin.plugin_id}")

        return await strategy.execute(context, plan)

    async def post_execute(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """Stage: POST_EXECUTION - Cleanup and temporary artifact management."""
        logger.info(f"[Orchestrator] Post-execution cleanup for plan {plan.plan_id}")
        return {"cleanup": "completed"}

    async def verify_remediation(self, context: RemediationContext, plan: ExecutionPlan) -> bool:
        """Stage: VERIFICATION - Run a security scan to verify the fix."""
        logger.info(f"[Orchestrator] Verifying remediation for plan {plan.plan_id}")
        # This would trigger a targeted security scan in the future
        return True

    async def finalize_execution(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """Stage: COMPLETION - Record final metrics and metadata."""
        logger.info(f"[Orchestrator] Finalizing execution for plan {plan.plan_id}")
        return {"finalized": True}

    async def rollback_execution(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """Coordinates the rollback using the strategy's rollback method."""
        logger.info(f"[Orchestrator] Initiating rollback for plan {plan.plan_id}")

        plugin = self.registry.get_capability(plan.capability_id)
        strategy = await plugin.get_strategy(plan.strategy_id)

        if strategy and strategy.rollback_status != "unsupported":
            try:
                result = await strategy.rollback(context, plan)
                await self._transition_state(plan, RemediationState.ROLLED_BACK, "Rollback successful")
                return result
            except Exception as e:
                logger.exception(f"[Orchestrator] Rollback execution failed: {e}")
                await self._transition_state(plan, RemediationState.FAILED, f"Rollback failed: {e}")
                return {"status": "rollback_failed", "error": str(e)}

        logger.warning(f"[Orchestrator] Rollback unsupported for strategy {plan.strategy_id}")
        await self._transition_state(plan, RemediationState.FAILED, "Rollback requested but unsupported")
        return {"status": "rollback_unsupported"}

    # ── Helpers ─────────────────────────────────────────────────────────────────────

    async def _transition_state(self, plan: ExecutionPlan, to_state: RemediationState, reason: str):
        """
        Atomic state transition using the StateMachine and DB persistence.
        """
        current_state = plan.status if isinstance(plan.status, RemediationState) else RemediationState.CREATED

        if not StateMachine.validate_transition(current_state, to_state):
            logger.error(f"[Orchestrator] Illegal transition {current_state} -> {to_state}")
            return

        # In a real implementation, this would update the DB model
        plan.status = to_state

        # Log the transition for audit
        history = RemediationStateHistory(
            plan_id=plan.plan_id,
            tenant_id=plan.tenant_id if hasattr(plan, 'tenant_id') else "unknown",
            from_state=current_state,
            to_state=to_state,
            transition_timestamp=datetime.now(timezone.utc),
            reason=reason
        )
        self.db.add(history)
        await self.db.commit()

    async def _emit_event(self, context: RemediationContext, plan: ExecutionPlan, event_type: RemediationEventType):
        """Publishes a lifecycle event to the event bus."""
        message = RemediationMessage(
            event_type=event_type,
            tenant_id=context.tenant_id,
            execution_id=plan.plan_id,
            correlation_id=context.correlation_id,
            source_component="ExecutionOrchestrator",
            payload={"plan_id": plan.plan_id, "status": plan.status}
        )
        await event_bus.publish(message)
