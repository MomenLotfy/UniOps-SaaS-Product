from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AlertResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    title: str
    message: Optional[str] = None
    severity: str
    category: Optional[str] = None
    source: Optional[str] = None
    status: str = "active"
    is_read: bool = False
    resource: Optional[str] = None
    metadata_: dict = {}
    fired_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AlertUpdate(BaseModel):
    status: Optional[str] = None
    is_read: Optional[bool] = None


class AlertStats(BaseModel):
    total: int = 0
    active: int = 0
    resolved: int = 0
    critical: int = 0
    high: int = 0
    unread: int = 0
