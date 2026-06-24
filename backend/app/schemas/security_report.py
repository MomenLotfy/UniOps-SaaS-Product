from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SecurityReportGenerate(BaseModel):
    name: str
    description: Optional[str] = None
    report_type: str
    format: str = "json"
    parameters: dict = {}
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class SecurityReportResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    report_type: str
    status: str
    format: str
    generated_by: str
    parameters: dict
    summary: dict
    findings: dict
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
