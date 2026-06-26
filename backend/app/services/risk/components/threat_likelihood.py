from __future__ import annotations
from app.services.risk.context import RiskContext
from app.utils.logger import logger

class ThreatLikelihoodEngine:
    """
    Estimates the probability of an attack based on current threat intelligence.
    """
    async def calculate(self, context: RiskContext) -> float:
        logger.info(f"[ThreatLikelihood] Estimating likelihood for {context.finding_id}")

        likelihood = 20.0 # Baseline

        # Increase likelihood if there is an active campaign targeting this product
        if context.enriched_finding.vulnerability and context.enriched_finding.vulnerability.threat_intel:
            ti = context.enriched_finding.vulnerability.threat_intel
            if ti.campaign:
                likelihood += 30.0
            if ti.threat_actor:
                likelihood += 20.0

        # Increase if exploit maturity is high
        if context.enriched_finding.exploit:
            maturity = context.enriched_finding.exploit.status.status
            if maturity == "Wild":
                likelihood += 40.0
            elif maturity == "Weaponized":
                likelihood += 20.0

        return min(100.0, likelihood)
