from __future__ import annotations
from typing import Tuple, List, Optional
from .context_builder import DecisionContext
from ..models.decision import Decision, DecisionPlan, DecisionStep, DecisionReason, DecisionEvidence
from ..models.policy import DecisionPolicyReference

class DecisionEngine:
    """
    Core deterministic logic for converting a validated context into a decision.
    """
    def __init__(self):
        # In a full implementation, this would load a set of active policies
        pass

    async def determine_decision(self, context: DecisionContext) -> Tuple[Decision, List[DecisionPlan], List[DecisionReason]]:
        """
        Applies policies to the context to produce a deterministic decision.
        """
        raw_data = context.raw_data
        risk_score = raw_data.get("risk", {}).get("overall_score", 0.0)

        # DETERMINISTIC LOGIC (Foundation Level):
        # If risk > 8.0 -> Critical Patch Required
        # If risk > 5.0 -> Mitigate
        # Else -> Monitor

        result = "MONITOR"
        reason_code = "LOW_RISK"
        description = "Risk score is below the threshold for active remediation."

        if risk_score > 8.0:
            result = "PATCH"
            reason_code = "HIGH_RISK_VULNERABILITY"
            description = "Critical risk score detected; immediate patching required."
        elif risk_score > 5.0:
            result = "MITIGATE"
            reason_code = "MEDIUM_RISK_VULNERABILITY"
            description = "Medium risk score detected; mitigation recommended."

        # 1. Create the Decision entity
        decision = Decision(
            tenant_id=context.tenant_id,
            correlation_id=context.correlation_id,
            context_id=context.id,
            final_result=result,
            status="READY", # Set by the pipeline, but we define the outcome here
            version=1
        )

        # 2. Create a simple Plan (Foundation Level)
        plan = DecisionPlan(
            decision_id=decision.id,
            execution_order=1,
            tenant_id=context.tenant_id,
            correlation_id=context.correlation_id
        )

        steps = [
            DecisionStep(
                plan_id=plan.id,
                step_type="VERIFY_ASSET_STATE",
                result="Succeeded",
                tenant_id=context.tenant_id,
                correlation_id=context.correlation_id
            ),
            DecisionStep(
                plan_id=plan.id,
                step_type=f"EXECUTE_{result}",
                result="Pending",
                tenant_id=context.tenant_id,
                correlation_id=context.correlation_id
            )
        ]

        # 3. Create the Reason
        reason = DecisionReason(
            decision_id=decision.id,
            reason_code=reason_code,
            description=description,
            tenant_id=context.tenant_id,
            correlation_id=context.correlation_id
        )

        return decision, [plan], [reason]
