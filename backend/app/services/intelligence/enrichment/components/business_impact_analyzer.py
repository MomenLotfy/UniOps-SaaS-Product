from __future__ import annotations
from typing import Any, Dict, List
from .base import IEnricher
from app.services.intelligence.enrichment.context import EnrichmentContext
from app.utils.logger import logger

class BusinessImpactAnalyzer(IEnricher):
    """
    Estimates the operational, financial, and compliance risk to the business.
    """
    async def enrich(self, context: EnrichmentContext) -> None:
        logger.info(f"[BusinessImpactAnalyzer] Analyzing business impact for {context.finding_id}")

        # Logic based on asset criticality and technical severity
        criticality = context.raw_metadata.get("asset_criticality", 1.0)
        severity = 0.0
        if context.vulnerability:
            severity = context.vulnerability.cvss_score or 0.0

        # Simple impact matrix
        impact_score = severity * criticality

        context.business_impact = {
            "operational_impact": "high" if impact_score > 7.0 else "medium" if impact_score > 4.0 else "low",
            "financial_risk": "significant" if impact_score > 8.0 else "moderate",
            "compliance_risk": "high" if severity > 7.0 else "medium",
            "customer_impact": "direct" if criticality > 2.0 else "indirect"
        }

        context.business_risk = impact_score
