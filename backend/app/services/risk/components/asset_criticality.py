from __future__ import annotations
from app.services.risk.context import RiskContext
from app.utils.logger import logger

class AssetCriticalityEngine:
    """
    Weights risk based on the asset's environment and role.
    """
    async def calculate(self, context: RiskContext) -> float:
        logger.info(f"[AssetCriticality] Evaluating asset for {context.finding_id}")

        # Environment weight
        env = context.enriched_finding.risk.factors.get("environment", "dev")
        env_weight = {
            "production": 1.0,
            "staging": 0.7,
            "dev": 0.3
        }.get(env, 0.1)

        # Role weight (Database > App Server > Utility)
        role = context.enriched_finding.risk.factors.get("asset_role", "unknown")
        role_weight = {
            "database": 1.2,
            "api_gateway": 1.1,
            "worker": 0.8
        }.get(role, 1.0)

        return min(100.0, 100.0 * env_weight * role_weight)
