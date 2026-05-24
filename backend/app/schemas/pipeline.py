from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class PipelineResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    integration_id: Optional[str] = None
    external_id: Optional[str] = None
    name: str
    repository: Optional[str] = None
    branch: str = "main"
    status: str
    stage: Optional[str] = None
    duration: Optional[int] = None
    triggered_by: Optional[str] = None
    commit_sha: Optional[str] = None
    commit_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    logs_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PipelineStats(BaseModel):
    total: int = 0
    running: int = 0
    success: int = 0
    failed: int = 0
    success_rate: float = 0.0
    avg_duration_seconds: float = 0.0


class PipelineTrigger(BaseModel):
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    variables: dict = {}


class PipelineJob(BaseModel):
    id: str
    name: str
    stage: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration: Optional[float] = None
    web_url: Optional[str] = None
    allow_failure: bool = False


class PipelineRerunResult(BaseModel):
    success: bool
    action: str                        # "rerun_all" | "rerun_failed" | "retry"
    pipeline_id: str                   # our DB id
    external_run_id: Optional[str] = None   # new run id from provider
    provider: str                      # "github" | "gitlab"
    message: str
    logs_url: Optional[str] = None
