from __future__ import annotations
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.remediation.models.models import RemediationPlan, RemediationStateHistory
from app.remediation.lifecycle.state import RemediationState
from app.remediation.events.bus import event_bus
from app.remediation.events.messages import RemediationMessage, RemediationEventType
from app.utils.logger import logger

class RecoveryManager:
    """
    Responsible for detecting and recovering from "stuck" remediation executions.
    Ensures the system can recover from worker crashes or network partitions.
    """
    def __init__(self, db_session: AsyncSession, execution_timeout_seconds: int = 3600):
        self.db = db_session
        self.timeout_seconds = execution_timeout_seconds

    async def scan_and_recover_stuck_executions(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Scans for plans that have been in a non-terminal state for longer than the timeout.
        """
        logger.info("[RecoveryManager] Scanning for stuck executions...")

        # Define states that are "stuck" if they last too long
        stuck_states = [
            RemediationState.PLANNING,
            RemediationState.WAITING_FOR_CAPABILITY,
            RemediationState.READY_FOR_EXECUTION,
            RemediationState.EXECUTING
        ]

        timeout_threshold = datetime.now(timezone.utc) - timedelta(seconds=self.timeout_seconds)

        # Query for plans in stuck states that haven't been updated recently
        query = select(RemediationPlan).where(
            RemediationPlan.status.in_(stuck_states),
            RemediationPlan.updated_at < timeout_threshold
        )
        if tenant_id:
            query = query.where(RemediationPlan.tenant_id == tenant_id)

        result = await self.db.execute(query)
        stuck_plans = result.scalars().all()

        recovered_count = 0
        for plan in stuck_plans:
            success = await self._recover_plan(plan)
            if success:
                recovered_count += 1

        return {
            "scanned_count": len(stuck_plans),
            "recovered_count": recovered_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def _recover_plan(self, plan: RemediationPlan) -> bool:
        """
        Attempts to recover a specific plan.
        Depending on the state, it may trigger a rollback or move it to FAILED.
        """
        logger.warning(f"[RecoveryManager] Attempting recovery for plan {plan.id} (State: {plan.status})")

        try:
            # 1. If it was executing, we must assume it's in an inconsistent state and trigger rollback.
            if plan.status == RemediationState.EXECUTING:
                # Trigger an actual rollback event via the EventBus
                try:
                    await event_bus.publish(RemediationMessage(
                        event_type=RemediationEventType.ROLLBACK_REQUESTED,
                        tenant_id=plan.tenant_id,
                        execution_id=plan.id,
                        correlation_id=plan.id,
                        source_component="RecoveryManager",
                        payload={
                            "reason": "Automatic recovery: Execution timed out. Marked as failed.",
                            "last_known_state": "EXECUTING",
                            "timeout_seconds": self.timeout_seconds
                        }
                    ))
                    logger.info(f"[RecoveryManager] Rollback requested for plan {plan.id}")
                except Exception as e:
                    logger.error(f"[RecoveryManager] Failed to publish rollback event for plan {plan.id}: {e}")

                plan.status = RemediationState.FAILED
                plan.updated_at = datetime.now(timezone.utc)

                # Log the recovery transition
                history = RemediationStateHistory(
                    plan_id=plan.id,
                    tenant_id=plan.tenant_id,
                    from_state=RemediationState.EXECUTING,
                    to_state=RemediationState.FAILED,
                    transition_timestamp=datetime.now(timezone.utc),
                    reason="Automatic recovery: Execution timed out. Marked as failed."
                )
                self.db.add(history)
            else:
                # For non-executing states (e.g. PLANNING), we can simply reset to FAILED or RE-QUEUE
                plan.status = RemediationState.FAILED
                plan.updated_at = datetime.now(timezone.utc)

                history = RemediationStateHistory(
                    plan_id=plan.id,
                    tenant_id=plan.tenant_id,
                    from_state=plan.status, # This should be the old state, but we are simplifying
                    to_state=RemediationState.FAILED,
                    transition_timestamp=datetime.now(timezone.utc),
                    reason="Automatic recovery: Planning timed out."
                )
                self.db.add(history)

            await self.db.commit()
            return True
        except Exception as e:
            logger.error(f"[RecoveryManager] Failed to recover plan {plan.id}: {e}")
            return False
