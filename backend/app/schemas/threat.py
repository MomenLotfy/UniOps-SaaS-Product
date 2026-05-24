from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ThreatResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    title: str
    description: Optional[str] = None
    severity: str
    category: Optional[str] = None
    source: Optional[str] = None
    status: str = "open"
    resource: Optional[str] = None
    namespace: Optional[str] = None
    ip: Optional[str] = None
    mitre_tactic: Optional[str] = None
    mitre_technique: Optional[str] = None
    raw_data: dict = {}
    detected_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ThreatUpdate(BaseModel):
    status: Optional[str] = None
    description: Optional[str] = None


class ThreatActionResult(BaseModel):
    success: bool
    action: str                        # "resolve" | "suppress"
    threat_id: str
    finding_id: Optional[str] = None   # AWS Security Hub finding ARN
    aws_processed: Optional[int] = None
    message: str


class ThreatStats(BaseModel):
    total: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    open: int = 0
    resolved: int = 0
