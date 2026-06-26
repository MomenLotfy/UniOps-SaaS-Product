from __future__ import annotations
from typing import Optional
import uuid
from app.remediation.interfaces.base import RemediationContext, ExecutionPlan
from app.remediation.registry.registry import CapabilityRegistry
from app.utils.logger import logger

class RemediationDecisionEngine:
    """
    Analyzes the security context and determines the optimal remediation path.
    Acts as the 'brain' that maps a finding to a concrete execution plan.
    """
    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    async def decide_remediation(self, context: RemediationContext) -> Optional[ExecutionPlan]:
        """
        Analyzes the context and determines the optimal remediation path.
        """
        logger.info(f"[DecisionEngine] Analyzing finding {context.finding_id} for tenant {context.tenant_id}")

        # 1. Identify the capability needed.
        # In a production environment, this would be determined by a mapping engine,
        # a rule-based system, or suggested by the Security Copilot AI.
        capability_id = self._determine_required_capability(context)
        if not capability_id:
            logger.warning(f"[DecisionEngine] No suitable capability found for finding {context.finding_id}")
            return None

        # 2. Resolve the capability to a plugin/handler.
        capability_handler = self.registry.get_capability(capability_id)
        if not capability_handler:
            logger.error(f"[DecisionEngine] Capability {capability_id} is registered but handler is missing")
            return None

        # 3. Resolve the specific strategy via the plugin.
        # The plugin (handler) knows which strategies it supports for this capability.
        try:
            # We first try to find a default strategy or let the plugin's
            # logic determine the best one based on context.
            # In our current interface, we might need a 'default' strategy ID or
            # an automated way to pick one.
            strategy = await capability_handler.resolve_strategy(context)
        except Exception as e:
            logger.error(f"[DecisionEngine] Strategy resolution failed: {e}")
            return None

        if not strategy:
            logger.warning(f"[DecisionEngine] No viable strategy found for capability {capability_id}")
            return None

        # 4. Construct the Execution Plan.
        plan = ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            finding_type=context.metadata.get("finding_type", "unknown"),
            target_technology=context.metadata.get("technology", "unknown"),
            capability_id=capability_id,
            strategy_id=strategy.strategy_id,
            priority=context.metadata.get("priority", "medium"),
            required_inputs=await strategy.get_required_inputs(context),
            expected_outputs=strategy.expected_outputs,
            status="draft"
        )

        logger.info(f"[DecisionEngine] Plan generated: {plan.plan_id} using strategy {plan.strategy_id}")
        return plan

    def _determine_required_capability(self, context: RemediationContext) -> Optional[str]:
        """
        Heuristic or logic to map context to a capability ID.
        """
        # This is a simplified mapping. In production, this would be a complex resolver.
        tech = context.metadata.get("technology", "").lower()
        finding_type = context.metadata.get("finding_type", "").lower()

        if "docker" in tech:
            return "DockerImageHardening"
        if "terraform" in tech:
            return "TfInfrastructureFix"
        if "dependency" in tech or "npm" in tech or "pip" in tech or "cve" in finding_type:
            return "DependencyUpgrade"

        return None
