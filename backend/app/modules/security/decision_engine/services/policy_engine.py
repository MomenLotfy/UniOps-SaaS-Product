from __future__ import annotations
from typing import Tuple, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from .policy_interfaces import IPolicyEngine, PolicyResolution
from .policy_repository import PolicyRepository
from ..models.policy import DecisionPolicy, PolicyEvaluation
from ..models.evidence import DecisionReason

class PolicyEngine(IPolicyEngine):
    """
    Transforms technical rule results into organizational decisions.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = PolicyRepository(db)

    async def apply_policy(
        self,
        context,
        technical_result: str,
        reasons: List[dict]
    ) -> Tuple[str, List[dict], PolicyResolution]:
        """
        Resolves the active policy and adjusts the final result.
        """
        # 1. Resolve the active policy for this context
        scope_data = {
            "repo_id": context.raw_data.get("asset_id"),
            "org_id": context.raw_data.get("org_id", "default_org")
        }
        policy = await self.repository.resolve_effective_policy(context.tenant_id, scope_data)

        if not policy:
            # No specific policy found, return technical result as is
            resolution = PolicyResolution(
                policy_id="N/A",
                policy_name="Default Platform Policy",
                final_result=technical_result,
                resolution_path="Global Fallback"
            )
            return technical_result, reasons, resolution

        # 2. Determine the final outcome based on policy logic
        # In this foundation: a policy can explicitly OVERRIDE the technical result.
        # Example: Policy "Critical Repo" requires PATCH even if RuleEngine said MONITOR.

        effective_result = technical_result
        is_overridden = False
        resolution_reason = "Policy aligned with technical result"

        # Check if policy is mandatory and requires a specific state
        if policy.is_mandatory:
            # Simplified logic: If policy is mandatory and we are in 'MONITOR',
            # but it's a 'CRITICAL' category policy, force 'MITIGATE'
            if technical_result == "MONITOR" and policy.category == "critical-infra":
                effective_result = "MITIGATE"
                is_overridden = True
                resolution_reason = "Mandatory Infrastructure Policy Override"

        # 3. Build the resolution object
        resolution = PolicyResolution(
            policy_id=policy.id,
            policy_name=policy.name,
            final_result=effective_result,
            resolution_path=f"Resolved to {policy.scope['type']} policy: {policy.name}",
            overridden=is_overridden,
            reason=resolution_reason
        )

        # 4. Audit the evaluation
        eval_record = PolicyEvaluation(
            tenant_id=context.tenant_id,
            decision_id=None, # To be updated by pipeline
            policy_id=policy.id,
            input_result=technical_result,
            output_result=effective_result,
            resolution_path=resolution.resolution_path,
            correlation_id=context.correlation_id,
            trace_id=context.trace_id
        )
        self.db.add(eval_record)

        return effective_result, reasons, resolution
