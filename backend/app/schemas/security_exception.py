from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SecurityExceptionCreate(BaseModel):
    policy_id: Optional[str] = None
    finding_id: Optional[str] = None
    finding_type: Optional[str] = None
    title: str
    justification: str
    risk_acceptance: str = ""
    exception_type: str = "temporary"
    expires_at: Optional[datetime] = None
    scope: dict = {}
    tags: dict = {}


class SecurityExceptionUpdate(BaseModel):
    title: Optional[str] = None
    justification: Optional[str] = None
    risk_acceptance: Optional[str] = None
    exception_type: Optional[str] = None
    expires_at: Optional[datetime] = None
    scope: Optional[dict] = None
    tags: Optional[dict] = None


class SecurityExceptionReview(BaseModel):
    action: str
    reviewer_note: Optional[str] = None


class SecurityExceptionResponse(BaseModel):
    id: str
    tenant_id: str
    policy_id: Optional[str]
    finding_id: Optional[str]
    finding_type: Optional[str]
    title: str
    justification: str
    risk_acceptance: str
    status: str
    exception_type: str
    requested_by: str
    approved_by: Optional[str]
    rejected_by: Optional[str]
    reviewer_note: Optional[str]
    expires_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    scope: dict
    tags: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
