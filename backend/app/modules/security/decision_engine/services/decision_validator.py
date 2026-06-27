from __future__ import annotations
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.vulnerability import Vulnerability
from app.models.risk import RiskAssessment

class DecisionValidator:
    """
    Validates that a decision request is legitimate and has a consistent context.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_request(self, tenant_id: str, source_finding_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validates tenant isolation and existence of the source finding.
        """
        # 1. Verify the finding exists and belongs to the tenant
        result = await self.db.execute(
            select(Vulnerability)
            .where(Vulnerability.id == source_finding_id)
            .where(Vulnerability.tenant_id == tenant_id)
        )
        finding = result.scalar_one_or_none()

        if not finding:
            return False, "Source finding not found or tenant isolation violation"

        # 2. Verify there is a corresponding risk assessment (required for decision)
        risk_result = await self.db.execute(
            select(RiskAssessment)
            .where(RiskAssessment.finding_id == source_finding_id)
            .where(RiskAssessment.tenant_id == tenant_id)
        )
        risk = risk_result.scalar_one_or_none()

        if not risk:
            return False, "Missing risk assessment for finding"

        return True, None

    async def validate_context_completeness(self, context_data: dict) -> Tuple[bool, Optional[str]]:
        """
        Ensures all required context fields are present before decision creation.
        """
        required_fields = ["finding_id", "risk_score", "asset_id", "environment"]
        for field in required_fields:
            if field not in context_data:
                return False, f"Missing required context field: {field}"

        return True, None
