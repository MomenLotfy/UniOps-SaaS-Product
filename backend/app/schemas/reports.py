from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# Report Status Types
class ReportStatus(str):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"


# Report Format Types
class ReportFormat(str):
    JSON = "json"
    PDF = "pdf"
    CSV = "csv"
    EXCEL = "excel"
    HTML = "html"


# Report Template Schema
class ReportTemplate(BaseModel):
    key: str
    name: str
    description: str
    category: str
    icon: Optional[str] = None
    enabled: bool = True
    required_permissions: List[str] = Field(default_factory=list)
    supported_formats: List[str] = Field(default_factory=lambda: ["json", "pdf", "csv", "excel"])
    default_params: Dict[str, Any] = Field(default_factory=dict)


# Report Schema
class Report(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: Optional[str] = None
    template: str
    status: str
    format: str
    created_by: str
    parameters: Dict[str, Any]
    summary: Dict[str, Any]
    findings: Dict[str, Any]
    metrics: Dict[str, Any] = Field(default_factory=dict)
    charts: Dict[str, Any] = Field(default_factory=dict)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    is_scheduled: bool = False
    schedule_cron: Optional[str] = None
    schedule_timezone: Optional[str] = None
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    recipients: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# Report Generation Request Schema
class ReportGenerateRequest(BaseModel):
    template: str
    name: Optional[str] = None
    description: Optional[str] = None
    format: str = "json"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    include_charts: bool = True
    include_findings: bool = True


# Report Schedule Request Schema
class ReportScheduleRequest(BaseModel):
    template: str
    name: str
    description: Optional[str] = None
    format: str = "json"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    schedule_cron: str  # Cron expression
    schedule_timezone: str = "UTC"
    recipients: List[str] = Field(default_factory=list)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


# Report List Query Parameters
class ReportListFilter(BaseModel):
    page: int = 1
    page_size: int = 50
    report_type: Optional[str] = None
    status: Optional[str] = None
    scheduled: Optional[bool] = None
    search: Optional[str] = None


# Report Summary Schema
class ReportSummary(BaseModel):
    total_reports: int
    completed_reports: int
    scheduled_reports: int
    failed_reports: int
    by_template: Dict[str, int]
    by_status: Dict[str, int]
    recent_reports: List[Dict[str, Any]]


# Export Result Schema
class ReportExportResult(BaseModel):
    filename: str
    content_type: str
    content: str
    size: int


# Download Request Schema
class DownloadRequest(BaseModel):
    report_id: str
    format: str = "json"
    include_charts: bool = True
    include_findings: bool = True


# Email Report Request Schema
class EmailReportRequest(BaseModel):
    report_id: str
    recipients: List[str]
    subject: Optional[str] = None
    body: Optional[str] = None
    include_charts: bool = True


# Regenerate Report Request Schema
class RegenerateReportRequest(BaseModel):
    parameters: Dict[str, Any] = Field(default_factory=dict)
    format: Optional[str] = None
    include_charts: bool = True
