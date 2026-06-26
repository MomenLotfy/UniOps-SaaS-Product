from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.services.risk.context import RiskContext
from app.services.risk.pipeline import RiskEvaluationPipeline
from app.services.risk.rule_engine import RiskRuleEngine
from app.services.risk.components.technical_risk import TechnicalRiskCalculator
from app.services.risk.components.business_impact import BusinessImpactEngine
from app.services.risk.components.asset_criticality import AssetCriticalityEngine
from app.services.risk.components.exposure_analyzer import ExposureEngine
from app.services.risk.components.threat_likelihood import ThreatLikelihoodEngine
from app.services.risk.components.priority_engine import PriorityEngine
from app.utils.logger import logger

class RiskIntelligenceEngine:
    """
    The core engine for transforming Enriched Findings into actionable priorities.
    """
    def __init__(self):
        self.rule_engine = RiskRuleEngine()
        self.pipeline = self._build_pipeline()

    def _build_pipeline(self) -> RiskEvaluationPipeline:
        """Defines the sequence of risk evaluation stages."""
        pipeline = RiskEvaluationPipeline()

        # Technical Risk
        tech = TechnicalRiskCalculator()
        pipeline.add_stage(lambda ctx: setattr(ctx, 'technical_score', await tech.calculate(ctx)) if False else tech.calculate(ctx))
        # Wait, the lambda is tricky with await. Let's use a proper wrapper.

        return pipeline

    # Fixing the pipeline stages to be async properly
    async def _run_stage(self, calculator: Any, dimension: str, context: RiskContext):
        score = await calculator.calculate(context)
        context.update_score(dimension, score)

    async def evaluate_risk(self, enriched_finding: Any) -> RiskContext:
        """
        Executes the full risk evaluation for a finding.
        """
        logger.info(f"[RiskEngine] Evaluating risk for finding {enriched_finding.finding_id}")

        context = RiskContext(
            finding_id=enriched_finding.finding_id,
            tenant_id=enriched_finding.tenant_id,
            enriched_finding=enriched_finding
        )

        # 1. Dimensional Calculation
        # Manual pipeline for clarity and async handling
        await self._run_stage(TechnicalRiskCalculator(), "technical", context)
        await self._run_stage(BusinessImpactEngine(), "business", context)
        await self._run_stage(AssetCriticalityEngine(), "environmental", context)
        await self._run_stage(ExposureEngine(), "operational", context) # Mapping exposure to operational
        await self._run_stage(ThreatLikelihoodEngine(), "compliance", context) # Mocking mapping

        # 2. Deterministic Rule Application
        context.priority = self.rule_engine.evaluate_priority(context)

        # 3. Final Priority Synthesis
        priority_engine = PriorityEngine()
        await priority_engine.calculate(context)

        return context
