from __future__ import annotations
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.vulnerability import Vulnerability
from app.models.risk import RiskAssessment
from ..models.context import DecisionContext

class DecisionContextBuilder:
    """
    Aggregates all information required for a decision from the platform.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_context(self, tenant_id: str, finding_id: str, correlation_id: str) -> DecisionContext:
        """
        Collects data from Security Finding, Risk, Assets, and Repository.
        """
        # 1. Fetch Security Finding
        finding_res = await self.db.execute(select(Vulnerability).where(Vulnerability.id == finding_id))
        finding = finding_res.scalar_one_or_none()

        # 2. Fetch Risk Intelligence
        risk_res = await self.db.execute(select(RiskAssessment).where(RiskAssessment.finding_id == finding_id))
        risk = risk_res.scalar_one_or_none()

        # 3. Build aggregate raw data
        # In a real implementation, we would call other services (Graph, Asset, etc.)
        # Here we simulate the aggregation of context
        raw_context = {
            "finding": {
                "id": finding.id if finding else None,
                "cve_id": finding.cve_id if finding else None,
                "severity": finding.severity if finding else None,
                "title": finding.title if finding else None,
            },
            "risk": {
                "overall_score": risk.overall_score if risk else None,
                "priority": risk.priority if risk else None,
                "confidence": risk.confidence_score if risk else None,
            },
            "environment": "production", # Mocked: would come from Asset service
            "asset_id": finding.repo_id if finding else "unknown", # Mocked
            "owner": "security-team", # Mocked: would come from Owner service
            "compliance": "SOC2, HIPAA", # Mocked
        }

        # 4. Create the model
        context = DecisionContext(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_finding_id=finding_id,
            raw_data=raw_context,
            version=1
        )

        return context
