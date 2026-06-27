from __future__ import annotations
from typing import Tuple, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from .rule_engine import RuleEngine
from .rule_repository import RuleRepository
from ..models.decision import Decision, DecisionPlan, DecisionStep, DecisionReason
from ..models.context import DecisionContext

class DecisionEngine:
    """
    Core deterministic logic for converting a validated context into a decision.
    Now powered by the Rule Engine.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def determine_decision(self, context: DecisionContext) -> Tuple[Decision, List[DecisionPlan], List[DecisionReason]]:
        """
        Evaluates the context using the Rule Engine to produce a deterministic decision.
        """
        # Initialize Rule Engine with its repository
        repo = RuleRepository(self.db)
        rule_engine = RuleEngine(self.db, repo)

        # Evaluate context against rules
        final_result, _, matched_reasons_data = await rule_engine.evaluate(context)

        # 1. Create the Decision entity
        decision = Decision(
            tenant_id=context.tenant_id,
            correlation_id=context.correlation_id,
            context_id=context.id,
            final_result=final_result,
            status="READY",
            version=1
        )

        # 2. Build a basic Plan based on the result
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

        # 3. Create Reasons from Rule Engine matches
        reasons = [
            DecisionReason(
                decision_id=decision.id,
                reason_code=r["code"],
                description=r["description"],
                tenant_id=context.tenant_id,
                correlation_id=context.correlation_id
            ) for r in matched_reasons_data
        ]

        # If no rules matched, provide a default reason
        if not reasons:
            reasons.append(DecisionReason(
                decision_id=decision.id,
                reason_code="DEFAULT_MONITOR",
                description="No specific rules matched; default to monitoring.",
                tenant_id=context.tenant_id,
                correlation_id=context.correlation_id
            ))

        return decision, [plan], reasons
