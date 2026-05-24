from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class PodResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    integration_id: Optional[str] = None
    name: str
    namespace: str = "default"
    cluster: Optional[str] = None
    status: str
    phase: Optional[str] = None
    node: Optional[str] = None
    cpu_request: Optional[float] = None
    cpu_limit: Optional[float] = None
    cpu_usage: Optional[float] = None
    memory_request: Optional[int] = None
    memory_limit: Optional[int] = None
    memory_usage: Optional[int] = None
    restart_count: int = 0
    containers: list = []
    labels: dict = {}
    created_at: datetime
    updated_at: datetime


class PodStats(BaseModel):
    total: int = 0
    running: int = 0
    pending: int = 0
    failed: int = 0
    cpu_usage_pct: float = 0.0
    memory_usage_pct: float = 0.0
    high_restart_count: int = 0


class PodActionResult(BaseModel):
    success: bool
    action: str                      # "delete" | "restart"
    pod_name: str
    namespace: str
    message: str
    has_controller: Optional[bool] = None   # None = not checked (delete path)
