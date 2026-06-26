from __future__ import annotations
from typing import Any, Dict, List
from .base import IEnricher
from app.services.intelligence.enrichment.context import EnrichmentContext
from app.utils.logger import logger

class TrustScoreCalculator(IEnricher):
    """
    Calculates the trust level of the intelligence based on provider provenance.
    """
    async def enrich(self, context: EnrichmentContext) -> None:
        logger.info(f"[TrustScoreCalculator] Calculating trust score for {context.finding_id}")

        # Average the trust scores from the provenance of resolved fields
        trusts = []

        if context.vulnerability and context.vulnerability.provenance:
            trusts.extend([p.trust_score for p in context.vulnerability.provenance.values()])

        if context.package and context.package.provenance:
            trusts.extend([p.trust_score for p in context.package.provenance.values()])

        if not trusts:
            context.trust_score = 0.5 # Default baseline
            return

        context.trust_score = sum(trusts) / len(trusts)
