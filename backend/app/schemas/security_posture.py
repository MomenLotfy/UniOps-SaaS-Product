from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class SecurityPostureResponse(BaseModel):
    id: str
    tenant_id: str
    overall_score: float
    threat_score: float
    vulnerability_score: float
    compliance_score: float
    asset_score: float
    policy_score: float
    breakdown: dict
    trend: str
    recorded_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class SecurityPostureSummary(BaseModel):
    current_score: float
    trend: str
    threat_score: float
    vulnerability_score: float
    compliance_score: float
    asset_score: float
    policy_score: float
    breakdown: dict
    history: list[dict]
    open_threats: int
    open_vulns: int
    critical_assets: int
    active_policies: int
    pending_exceptions: int
