from __future__ import annotations
from app.services.risk.context import RiskContext
from app.utils.logger import logger

class BusinessImpactEngine:
    """
    Analyzes the potential business impact of a vulnerability.
    """
    async def calculate(self, context: RiskContext) -> float:
        logger.info(f"[BusinessImpact] Analyzing impact for {context.finding_id}")

        # Base impact is derived from asset criticality
        criticality = context.enriched_finding.risk.factors.get("asset_criticality", 1.0)

        # Revenue / Customer Impact logic
        impact_score = criticality * 20.0

        # Add penalty for critical services (e.g. Auth, Billing)
        service = context.enriched_finding.package.name if context.enriched_finding.package else "unknown"
        if service in ["auth-service", "payment-gateway", "core-api"]:
            impact_score += 30.0

        return min(100.0, impact_score)
