from datetime import date, datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


# =========================
# Cost Metrics
# =========================
class CostMetricResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    integration_id: Optional[str] = None
    provider: str
    service: Optional[str] = None
    region: Optional[str] = None
    amount: float
    currency: str = "USD"
    period_start: date
    period_end: date
    tags: Dict[str, Any] = {}
    breakdown: Dict[str, Any] = {}
    created_at: datetime


# =========================
# Cost Summary
# =========================
class CostSummary(BaseModel):
    total_cost: float
    currency: str = "USD"
    trend_pct: float = 0.0
    mtd_cost: float = 0.0
    forecast_eom: float = 0.0
    by_provider: Dict[str, Any] = {}
    by_service: Dict[str, Any] = {}
    by_region: Dict[str, Any] = {}


# =========================
# Cost Anomalies
# =========================
class CostAnomalyResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    service: Optional[str] = None
    expected_cost: float
    actual_cost: float
    deviation: float
    severity: str
    status: str = "open"
    detected_date: date
    description: Optional[str] = None
    created_at: datetime


# =========================
# Savings (DB / API Model)
# =========================
class SavingsResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None   # rightsizing | s3_lifecycle | reserved_instance | stop_instance
    provider: Optional[str] = None   # aws | gcp | azure
    potential_savings: float
    currency: str = "USD"
    effort: str = "medium"
    status: str = "open"
    resource: Optional[str] = None
    recommendation: Optional[str] = None
    created_at: datetime


# =========================
# Action Result (Execution Response)
# =========================
class SavingActionResult(BaseModel):
    success: bool
    saving_id: str
    category: str
    aws_action: str
    resource: Optional[str] = None
    message: str
    error: Optional[str] = None
