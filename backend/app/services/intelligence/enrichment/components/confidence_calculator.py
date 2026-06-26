from __future__ import annotations
from typing import Any, Dict, List
from .base import IEnricher
from app.services.intelligence.enrichment.context import EnrichmentContext
from app.utils.logger import logger

class ConfidenceCalculator(IEnricher):
    """
    Quantifies the reliability of the enrichment result.
    """
    async def enrich(self, context: EnrichmentContext) -> None:
        logger.info(f"[ConfidenceCalculator] Calculating confidence for {context.finding_id}")

        score = 0.0
        factors = []

        # 1. Vulnerability presence
        if context.vulnerability:
            score += 0.4
            factors.append("vulnerability_present")

        # 2. Package precision
        if context.package:
            score += 0.3
            factors.append("package_resolved")

        # 3. Exploit confirmation
        if context.exploit:
            score += 0.3
            factors.append("exploit_confirmed")

        context.confidence_score = min(1.0, score)
        context.add_metadata("confidence_factors", factors)
