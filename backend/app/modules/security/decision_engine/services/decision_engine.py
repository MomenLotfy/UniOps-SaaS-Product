from __future__ import annotations
from typing import Tuple, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from .rule_engine import RuleEngine
from .rule_repository import RuleRepository
from .policy_engine import PolicyEngine
from ..models.decision import Decision
from ..models.plan import DecisionPlan, DecisionStep
from ..models.evidence import DecisionReason
from ..models.context import DecisionContext

class DecisionEngine:
    """
    Core deterministic logic for converting a validated context into a decision.
    Orchestrates the Rule Engine and the Enterprise Policy Engine.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def determine_decision(self, context: DecisionContext) -> Tuple[Decision, List[DecisionPlan], List[DecisionReason], Any]:
        """
        Evaluates the context using Rules and Policies to produce a deterministic decision.
        """
        # 1. Technical Evaluation (Rule Engine)
        rule_repo = RuleRepository(self.db)
        rule_engine = RuleEngine(self.db, rule_repo)
        technical_result, _, matched_reasons_data = await rule_engine.evaluate(context)

        # 2. Organizational Overlay (Policy Engine)
        policy_engine = PolicyEngine(self.db)
        final_result, updated_reasons_data, resolution = await policy_engine.apply_policy(
            context=context,
            technical_result=technical_result,
            reasons=matched_reasons_data
        )

        # 3. Create the Decision entity
        decision = Decision(
            tenant_id=context.tenant_id,
            correlation_id=context.correlation_id,
            context_id=context.id,
            final_result=final_result,
            status="READY",
            version=1
        )

        # 4. Build a basic Plan based on the final policy result
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
                step_type=f"EXECUTE_{final_result}",
                result="Pending",
                tenant_id=context.tenant_id,
                correlation_id=context.correlation_id
            )
        ]

        # 5. Create Reasons from both Rule Engine and Policy Engine
        reasons = [
            DecisionReason(
                decision_id=decision.id,
                reason_code=r["code"],
                description=r["description"],
                tenant_id=context.tenant_id,
                correlation_id=context.correlation_id
            ) for r in updated_reasons_data
        ]

        # Add the policy resolution as a final reason
        reasons.append(DecisionReason(
            decision_id=decision.id,
            reason_code="POLICY_RESOLUTION",
            description=f"Resolved via {resolution.policy_name}: {resolution.reason}",
            tenant_id=context.tenant_id,
            correlation_id=context.correlation_id
        ))

        return decision, [plan], reasons, resolution
