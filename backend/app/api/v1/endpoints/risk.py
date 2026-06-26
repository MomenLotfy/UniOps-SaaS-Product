from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Optional

from app.api.deps import get_db
from app.services.risk.engine import RiskIntelligenceEngine
from app.services.risk.repository_risk import RepositoryRiskCalculator
from app.schemas.risk import RiskBreakdown, RepositoryRiskSummary
from app.services.intelligence.service import IntelligenceService

router = APIRouter()

@router.get("/{finding_id}", response_model=RiskBreakdown)
async def get_finding_risk(
    finding_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the detailed risk breakdown for a specific finding.
    """
    # 1. Get enriched finding from IntelligenceService
    intel_service = IntelligenceService(db)
    enriched = await intel_service.get_enriched_finding(finding_id)

    if not enriched:
        raise HTTPException(status_code=404, detail="Enriched finding not found")

    # 2. Calculate risk
    risk_engine = RiskIntelligenceEngine()
    context = await risk_engine.evaluate_risk(enriched)

    # 3. Map to schema
    return RiskBreakdown(
        technical_risk={"score": context.technical_score, "confidence": context.confidence, "provenance": "TechnicalRiskCalculator"},
        business_risk={"score": context.business_score, "confidence": context.confidence, "provenance": "BusinessImpactEngine"},
        environmental_risk={"score": context.environmental_score, "confidence": context.confidence, "provenance": "AssetCriticalityEngine"},
        operational_risk={"score": context.operational_score, "confidence": context.confidence, "provenance": "ExposureEngine"},
        compliance_risk={"score": context.compliance_score, "confidence": context.confidence, "provenance": "ThreatLikelihoodEngine"},
        overall_score=context.overall_score,
        priority=context.priority
    )

@router.get("/repositories", response_model=List[RepositoryRiskSummary])
async def get_repository_risks(
    db: AsyncSession = Depends(get_db)
):
    """
    Lists repositories sorted by their aggregate risk score.
    """
    calc = RepositoryRiskCalculator(db)
    # Mocking a list of repos for the result
    repos = ["core-api", "payment-gateway", "auth-service"]
    results = []
    for repo in repos:
        risk = await calc.calculate_repo_risk(repo, "tenant-1")
        results.append(RepositoryRiskSummary(
            repository_id=repo,
            overall_risk_score=risk["overall_score"],
            priority_level=risk["priority"],
            critical_findings_count=0,
            high_findings_count=0,
            trend="stable",
            last_calculated_at=datetime.utcnow()
        ))

    return results
