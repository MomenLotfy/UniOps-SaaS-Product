from __future__ import annotations
from app.services.risk.context import RiskContext
from app.utils.logger import logger

class ExposureEngine:
    """
    Analyzes the network and cloud exposure of the affected asset.
    """
    async def calculate(self, context: RiskContext) -> float:
        logger.info(f"[ExposureEngine] Analyzing exposure for {context.finding_id}")

        score = 0.0

        # Check internet exposure in raw metadata
        is_public = context.enriched_finding.risk.factors.get("is_public_endpoint", False)
        if is_public:
            score += 50.0

        # Check network reachability
        reachability = context.enriched_finding.risk.factors.get("network_reachability", "internal")
        if reachability == "public":
            score += 30.0
        elif reachability == "dmz":
            score += 20.0

        return min(100.0, score)
