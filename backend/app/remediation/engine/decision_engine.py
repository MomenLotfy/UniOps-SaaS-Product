from __future__ import annotations
from typing import Optional, Any, Dict, List
import uuid

from app.remediation.interfaces.base import RemediationContext, ExecutionPlan
from app.remediation.registry.registry import CapabilityRegistry
from app.remediation.engine.classification.classifier import FindingClassifier, ClassificationResult
from app.remediation.engine.detection.detector import TechnologyDetector, DetectionResult
from app.remediation.engine.approval_engine import ApprovalEngine, ApprovalDecision
from app.remediation.engine.estimator import RemediationEstimator, ExecutionEstimate
from app.remediation.engine.rule_engine import RuleEngine
from app.remediation.engine.ai_support import DecisionSupportAI
from app.utils.logger import logger

class RemediationDecisionEngine:
    """
    The Brain of the Remediation Platform.
    Coordinates classification, technology detection, rule evaluation,
    and AI support to produce a deterministic Execution Plan.
    """
    def __init__(
        self,
        registry: CapabilityRegistry,
        ai_support: Optional[DecisionSupportAI] = None
    ):
        self.registry = registry
        self.classifier = FindingClassifier()
        self.tech_detector = TechnologyDetector()
        self.approval_engine = ApprovalEngine()
        self.estimator = RemediationEstimator()
        self.rule_engine = RuleEngine()
        self.ai_support = ai_support

    async def create_execution_plan(self, context: RemediationContext) -> Optional[ExecutionPlan]:
        """
        Full decision pipeline: Finding -> Classification -> Detection -> Rule Engine -> Plan.
        """
        logger.info(f"[DecisionEngine] Planning remediation for finding {context.finding_id}")

        try:
            # 1. Finding Classification
            classification = await self.classifier.classify(context.metadata)

            # 2. Technology Detection
            tech_result = await self.tech_detector.detect(context.metadata)
            if tech_result.technology == "unknown":
                logger.error(f"[DecisionEngine] Could not detect technology for finding {context.finding_id}")
                return None

            # 3. Rule-Based Resolution
            # We use the rule engine to determine the best capability and strategy.
            rule_match = await self.rule_engine.evaluate(
                classification.category.value,
                tech_result.technology.value
            )

            if not rule_match:
                # Fallback to basic capability negotiation if no rule matches
                cap_id = await self._negotiate_best_capability(
                    tech_result.technology,
                    classification.category,
                    classification.suggested_capabilities
                )
                if not cap_id:
                    return None

                capability_handler = self.registry.get_capability(cap_id)
                if not capability_handler:
                    return None

                strategy = await capability_handler.resolve_strategy(context)
                if not strategy:
                    return None

                cap_id, strat_id, req_approval, priority = cap_id, strategy.strategy_id, False, "medium"
            else:
                cap_id, strat_id, req_approval, priority = rule_match

            # Validate that the resolved capability actually exists in the registry
            if not self.registry.get_capability(cap_id):
                logger.error(f"[DecisionEngine] Rule matched capability {cap_id} but it's not registered")
                return None

            # 4. AI Decision Support (Optional)
            ai_insight = None
            if self.ai_support:
                ai_insight = await self.ai_support.get_planning_insights(context)

            # 5. Risk & Approval Decision
            approval = await self.approval_engine.determine_approval(
                context.metadata,
                context.metadata.get("repo_metadata", {})
            )

            # 6. Execution Estimation
            estimate = await self.estimator.estimate(strat_id)

            # 7. Final Execution Plan Construction
            plan = ExecutionPlan(
                plan_id=str(uuid.uuid4()),
                finding_id=context.finding_id,
                finding_type=classification.category.value,
                target_technology=tech_result.technology.value,
                capability_id=cap_id,
                strategy_id=strat_id,
                priority=priority or context.metadata.get("priority", "medium"),
                risk_level=estimate.business_risk,
                confidence_score=classification.confidence if not ai_insight else (classification.confidence + ai_insight.confidence_score) / 2,
                estimated_impact=estimate.difficulty,
                required_inputs=await self.registry.get_capability(cap_id).get_strategy(strat_id).get_required_inputs(context) if self.registry.get_capability(cap_id) else {},
                expected_outputs=self.registry.get_capability(cap_id).get_strategy(strat_id).expected_outputs if self.registry.get_capability(cap_id) else [],
                approval_required=req_approval or approval.requires_approval,
                approval_role=approval.approval_role.value if approval.approval_role else None,
                rollback_available=True,
                validation_requirements=["post_execution_scan"],
                estimated_duration_seconds=60 * (1 if estimate.difficulty == "low" else 5 if estimate.difficulty == "medium" else 15),
                human_summary=ai_insight.summary if ai_insight else f"Remediate {classification.category.value} in {tech_result.technology.value}",
                status="draft"
            )

            logger.info(f"[DecisionEngine] Successfully generated plan {plan.plan_id}")
            return plan

        except Exception as e:
            logger.exception(f"[DecisionEngine] Critical failure during planning for {context.finding_id}: {e}")
            return None

    async def _negotiate_best_capability(self, tech, category, suggestions: List[str]) -> Optional[str]:
        """
        Negotiates with the Capability Registry to find the best plugin.
        """
        for cap_id in suggestions:
            plugin = self.registry.get_capability(cap_id)
            if plugin and tech.value in plugin.supported_technologies and category.value in plugin.supported_finding_types:
                return cap_id

        all_plugins = self.registry.list_plugins()
        for plugin_meta in all_plugins:
            plugin = self.registry.get_plugin(plugin_meta["id"])
            if plugin and tech.value in plugin.supported_technologies and category.value in plugin.supported_finding_types:
                return plugin.supported_capabilities[0]

        return None
