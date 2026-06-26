from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class SecurityPolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    severity: str = "medium"
    enforcement: str = "advisory"
    scope: dict = {}
    rules: list = []
    effective_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    frameworks: list = []
    tags: dict = {}


class SecurityPolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    enforcement: Optional[str] = None
    scope: Optional[dict] = None
    rules: Optional[list] = None
    effective_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    frameworks: Optional[list] = None
    tags: Optional[dict] = None


class SecurityPolicyResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    category: str
    severity: str
    status: str
    enforcement: str
    scope: dict
    rules: list
    exceptions_count: int
    violations_count: int
    created_by: Optional[str]
    updated_by: Optional[str]
    effective_date: Optional[datetime]
    review_date: Optional[datetime]
    frameworks: list
    tags: dict
    is_builtin: bool = False
    policy_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
