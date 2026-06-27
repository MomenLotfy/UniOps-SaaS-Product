from __future__ import annotations
from typing import Any, Dict, Optional, List
from datetime import datetime
from app.schemas.intelligence import (
    EnrichedFinding, CanonicalCVE, CanonicalPackage,
    CanonicalExploit, CanonicalWeakness, CanonicalAttackPattern,
    CanonicalRisk, ConfidenceLevel
)
from .context import EnrichmentContext
from .pipeline import EnrichmentPipeline
from .components.reference_enricher import ReferenceEnricher
from .components.patch_analyzer import PatchAnalyzer
from .components.exploit_analyzer import ExploitAnalyzer
from .components.asset_context_resolver import AssetContextResolver
from .components.business_impact_analyzer import BusinessImpactAnalyzer
from .components.recommendation_enricher import RecommendationEnricher
from .components.timeline_enricher import TimelineEnricher
from .components.confidence_calculator import ConfidenceCalculator
from .components.trust_score_calculator import TrustScoreCalculator
from app.utils.logger import logger

class EnrichmentEngine:
    """
    The primary orchestrator for security intelligence enrichment.
    Transforms Canonical Intelligence into a final EnrichedFinding.
    """
    def __init__(self, intelligence_service: Any):
        self.intel_service = intelligence_service
        self.pipeline = self._build_pipeline()

    def _build_pipeline(self) -> EnrichmentPipeline:
        """Defines the order of enrichment stages."""
        pipeline = EnrichmentPipeline()
        pipeline.add_stage(ReferenceEnricher())
        pipeline.add_stage(PatchAnalyzer())
        pipeline.add_stage(ExploitAnalyzer())
        pipeline.add_stage(AssetContextResolver())
        pipeline.add_stage(BusinessImpactAnalyzer())
        pipeline.add_stage(TimelineEnricher())
        pipeline.add_stage(ConfidenceCalculator())
        pipeline.add_stage(TrustScoreCalculator())
        pipeline.add_stage(RecommendationEnricher())
        return pipeline

    async def enrich(self, finding_id: str, tenant_id: str, raw_metadata: Dict[str, Any]) -> EnrichedFinding:
        """
        Executes the full enrichment pipeline.
        """
        logger.info(f"[EnrichmentEngine] Starting enrichment pipeline for finding {finding_id}")

        # 1. Initialize Context
        context = EnrichmentContext(
            finding_id=finding_id,
            tenant_id=tenant_id,
            raw_metadata=raw_metadata
        )

        # 2. Fetch Canonical Intelligence (Input to pipeline)
        cve_id = raw_metadata.get("cve_id")
        purl = raw_metadata.get("purl")

        if cve_id:
            context.vulnerability = await self.intel_service.get_vulnerability(cve_id)
            context.exploit = await self.intel_service.get_exploit(cve_id)

        if purl:
            context.package = await self.intel_service.get_package(purl)

        # 3. Run Pipeline
        await self.pipeline.execute(context)

        # 4. Calculate Final Overall Risk (Combining technical, business, and environmental)
        # This would normally use the RiskCalculator service
        overall_risk_score = (context.technical_risk * 0.4) + (context.business_risk * 0.6)
        # Normalize to 0-100
        final_score = min(100.0, max(0.0, overall_risk_score * 10))

        # 5. Assemble Final EnrichedFinding
        return EnrichedFinding(
            finding_id=finding_id,
            tenant_id=tenant_id,
            vulnerability=context.vulnerability,
            package=context.package,
            exploit=context.exploit,
            risk=CanonicalRisk(
                score=final_score,
                level="HIGH" if final_score > 70 else "MEDIUM" if final_score > 40 else "LOW",
                factors={
                    "technical": context.technical_risk,
                    "business": context.business_risk,
                    "confidence": context.confidence_score,
                    "trust": context.trust_score
                },
                confidence=ConfidenceLevel.HIGH if context.confidence_score > 0.8 else ConfidenceLevel.MEDIUM
            ),
            remediation_refs=[ref for ref in context.references],
            fix_available=len(context.patches) > 0,
            patched_versions=[p["version"] for p in context.patches],
            confidence=ConfidenceLevel.HIGH if context.confidence_score > 0.8 else ConfidenceLevel.MEDIUM,
            providers_used=await self.intel_service.get_active_providers(),
            last_enriched_at=datetime.utcnow()
        )
