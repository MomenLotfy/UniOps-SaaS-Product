from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TenantBase(BaseModel):
    name: str
    slug: str
    domain: Optional[str] = None
    logo_url: Optional[str] = None
    plan: str = "free"


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    logo_url: Optional[str] = None
    settings: Optional[dict] = None


class TenantResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    slug: str
    domain: Optional[str] = None
    logo_url: Optional[str] = None
    plan: str
    is_active: bool
    settings: dict = {}
    created_at: datetime
    updated_at: datetime


class TenantStats(BaseModel):
    total_users: int = 0
    total_integrations: int = 0
    active_pipelines: int = 0
    open_threats: int = 0
    monthly_cost: float = 0.0


class DomainVerificationRequest(BaseModel):
    domain: str


class DomainVerificationResponse(BaseModel):
    domain: str
    txt_record: str
    verified: bool = False
