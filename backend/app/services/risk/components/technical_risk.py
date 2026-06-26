from __future__ import annotations
from app.services.risk.context import RiskContext
from app.utils.logger import logger

class TechnicalRiskCalculator:
    """
    Evaluates technical risk based on CVSS, EPSS, and exploit intelligence.
    """
    async def calculate(self, context: RiskContext) -> float:
        logger.info(f"[TechnicalRisk] Calculating risk for {context.finding_id}")

        score = 0.0
        vulnerability = context.enriched_finding.vulnerability

        if not vulnerability:
            return 0.0

        # 1. Base CVSS Score (0-100 scale)
        cvss = vulnerability.cvss_score or 0.0
        score = cvss * 10.0

        # 2. Exploit Multiplier
        if context.enriched_finding.exploit:
            maturity = context.enriched_finding.exploit.status.status
            if maturity == "Wild":
                score += 20.0
            elif maturity == "Weaponized":
                score += 15.0
            elif maturity == "Functional":
                score += 10.0

        # 3. Attack Vector Penalty
        # (In a real implementation, we'd extract attack vector from CVSS vector string)
        # if "AV:N" in vulnerability.cvss_vector: score += 5.0

        return min(100.0, score)
