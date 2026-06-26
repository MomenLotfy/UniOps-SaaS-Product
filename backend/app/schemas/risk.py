from __future__ import annotations
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class RiskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"

class RiskScore(BaseModel):
    """Standardized risk score with confidence and provenance."""
    score: float = Field(..., ge=0.0, le=100.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    provenance: str # The component/rule that produced this score

class RiskBreakdown(BaseModel):
    """Detailed scores for different risk dimensions."""
    technical_risk: RiskScore
    business_risk: RiskScore
    environmental_risk: RiskScore
    operational_risk: RiskScore
    compliance_risk: RiskScore
    overall_score: float
    priority: RiskPriority

class RepositoryRiskSummary(BaseModel):
    """Aggregated risk metrics for a repository."""
    repository_id: str
    overall_risk_score: float
    priority_level: RiskPriority
    critical_findings_count: int
    high_findings_count: int
    trend: str # "increasing", "stable", "decreasing"
    last_calculated_at: datetime

class AssetRiskProfile(BaseModel):
    """Risk associated with a specific asset (cluster, namespace, etc)."""
    asset_id: str
    asset_type: str
    risk_score: float
    priority_level: RiskPriority
    top_contributors: List[str] # Finding IDs
