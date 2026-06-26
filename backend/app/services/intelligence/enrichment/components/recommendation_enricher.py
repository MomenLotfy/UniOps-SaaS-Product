from __future__ import annotations
from typing import Any, Dict, List
from .base import IEnricher
from app.services.intelligence.enrichment.context import EnrichmentContext
from app.utils.logger import logger

class RecommendationEnricher(IEnricher):
    """
    Produces deterministic remediation metadata and actionable recommendations.
    """
    async def enrich(self, context: EnrichmentContext) -> None:
        logger.info(f"[RecommendationEnricher] Generating recommendations for {context.finding_id}")

        recommendations = []

        # 1. Patch-based recommendation
        if context.patches:
            best_patch = context.patches[0]
            recommendations.append({
                "type": "upgrade",
                "action": f"Upgrade to version {best_patch['version']}",
                "confidence": best_patch["confidence"],
                "priority": "high" if context.overall_risk > 70 else "medium",
                "url": best_patch["url"]
            })

        # 2. Configuration-based recommendation (fallback)
        if not context.patches and context.vulnerability:
            recommendations.append({
                "type": "mitigation",
                "action": "Apply vendor-recommended configuration hardening",
                "confidence": "medium",
                "priority": "medium",
                "url": "https://example.com/hardening-guide"
            })

        # 3. No-patch scenario
        if not context.patches and not context.vulnerability:
            recommendations.append({
                "type": "manual_review",
                "action": "Perform manual security audit of the affected component",
                "confidence": "low",
                "priority": "low"
            })

        context.recommendations = recommendations
