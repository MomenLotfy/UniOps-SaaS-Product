from __future__ import annotations
from app.services.risk.context import RiskContext
from app.utils.logger import logger

class PriorityEngine:
    """
    Synthesizes all risk scores into a final priority and overall risk score.
    """
    async def calculate(self, context: RiskContext) -> None:
        logger.info(f"[PriorityEngine] Finalizing risk scores for {context.finding_id}")

        # Weights for the overall risk score
        weights = {
            "technical": 0.3,
            "business": 0.3,
            "environmental": 0.2,
            "operational": 0.1,
            "compliance": 0.1
        }

        overall = (
            (context.technical_score * weights["technical"]) +
            (context.business_score * weights["business"]) +
            (context.environmental_score * weights["environmental"]) +
            (context.operational_score * weights["operational"]) +
            (context.compliance_score * weights["compliance"])
        )

        context.overall_score = overall
        # Priority is set by the RiskRuleEngine, but we provide a baseline based on score
        if not context.priority or context.priority == "medium":
            if overall > 80: context.priority = "critical"
            elif overall > 60: context.priority = "high"
            elif overall > 30: context.priority = "medium"
            else: context.priority = "low"
