from __future__ import annotations
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.risk import RepositoryRiskProfile, RiskAssessment
from app.services.risk.engine import RiskIntelligenceEngine
from app.utils.logger import logger

class RepositoryRiskCalculator:
    """
    Aggregates individual finding risks to produce a repository-level rating.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_repo_risk(self, repository_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Calculates the aggregate risk score for a repository.
        """
        # Fetch all risk assessments for findings in this repo
        # (In a real system, we'd join with a findings table)
        result = await self.db.execute(
            select(RiskAssessment).where(RiskAssessment.tenant_id == tenant_id)
        )
        assessments = result.scalars().all()

        if not assessments:
            return {"overall_score": 0.0, "priority": "informational"}

        # Simple aggregation: weighted average of overall scores
        scores = [a.overall_score for a in assessments]
        avg_score = sum(scores) / len(scores)

        # Determine aggregate priority
        priority = "low"
        if any(a.priority == "critical" for a in assessments):
            priority = "critical"
        elif any(a.priority == "high" for a in assessments):
            priority = "high"
        elif avg_score > 50:
            priority = "medium"

        return {
            "repository_id": repository_id,
            "overall_score": avg_score,
            "priority": priority,
            "count": len(assessments)
        }
