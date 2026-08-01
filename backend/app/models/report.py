from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Report(BaseModel):
    """Enterprise Report model with scheduling, templates, and export support."""
    __tablename__ = "reports"

    tenant_id:    Mapped[str]           = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    name:         Mapped[str]           = mapped_column(String(255), nullable=False)
    description:  Mapped[str | None]    = mapped_column(Text)
    template:     Mapped[str]           = mapped_column(String(100), nullable=False)  # Report template type
    status:       Mapped[str]           = mapped_column(String(50), default="pending")  # pending, generating, completed, failed, scheduled
    format:       Mapped[str]           = mapped_column(String(20), default="json")  # json, pdf, csv, excel, html
    created_by:   Mapped[str]           = mapped_column(String(36), nullable=False, index=True)
    parameters:   Mapped[dict]          = mapped_column(JSON, default=dict)
    summary:      Mapped[dict]          = mapped_column(JSON, default=dict)
    findings:     Mapped[dict]          = mapped_column(JSON, default=dict)
    metrics:      Mapped[dict]          = mapped_column(JSON, default=dict)  # Additional metrics for charts
    charts:       Mapped[dict]          = mapped_column(JSON, default=dict)  # Chart data
    period_start: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    period_end:   Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    error:        Mapped[str | None]    = mapped_column(Text)

    # Scheduling
    is_scheduled: Mapped[bool]          = mapped_column(Boolean, default=False)
    schedule_cron: Mapped[str | None]   = mapped_column(String(100))  # Cron expression
    schedule_timezone: Mapped[str | None] = mapped_column(String(50))
    next_run_at:  Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    last_run_at:  Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    recipients:   Mapped[list]          = mapped_column(JSON, default=list)  # Email recipients

    # Export metadata
    export_file_key: Mapped[str | None] = mapped_column(String(255))  # S3 key or file path
    export_format:  Mapped[str]         = mapped_column(String(20), default="json")


class ReportTemplate(BaseModel):
    """Pre-defined report templates with metadata."""
    __tablename__ = "report_templates"

    key:          Mapped[str]           = mapped_column(String(100), primary_key=True)
    name:         Mapped[str]           = mapped_column(String(255), nullable=False)
    description:  Mapped[str]           = mapped_column(Text)
    category:     Mapped[str]           = mapped_column(String(50), default="security")
    icon:         Mapped[str | None]    = mapped_column(String(50))
    enabled:      Mapped[bool]          = mapped_column(Boolean, default=True)
    required_permissions: Mapped[list]  = mapped_column(JSON, default=list)
    supported_formats: Mapped[list]    = mapped_column(JSON, default=["json", "pdf", "csv", "excel"])
    default_params: Mapped[dict]       = mapped_column(JSON, default=dict)


# Report template definitions (stored in DB on migration)
REPORT_TEMPLATES = [
    # Executive Reports
    {"key": "executive_security_report", "name": "Executive Security Report", "category": "executive", "icon": "Shield", "description": "High-level security posture and risk assessment for executives"},
    {"key": "risk_trend_report", "name": "Risk Trend Report", "category": "executive", "icon": "TrendingUp", "description": "Security risk trends over time with visualizations"},
    {"key": "attack_surface_report", "name": "Attack Surface Report", "category": "executive", "icon": "Target", "description": "Comprehensive attack surface analysis and exposure assessment"},

    # Security Reports
    {"key": "vulnerability_report", "name": "Vulnerability Report", "category": "security", "icon": "AlertTriangle", "description": "Detailed vulnerability assessment and remediation status"},
    {"key": "threat_intelligence_report", "name": "Threat Intelligence Report", "category": "security", "icon": "Eye", "description": "Current threats, indicators, and attack patterns"},
    {"key": "repository_security_report", "name": "Repository Security Report", "category": "security", "icon": "FileCode", "description": "Security findings from repository scans"},
    {"key": "iam_report", "name": "IAM Report", "category": "security", "icon": "Users", "description": "Identity and access management audit"},
    {"key": "secrets_exposure_report", "name": "Secrets Exposure Report", "category": "security", "icon": "Key", "description": "Detected secrets and sensitive data exposure"},

    # Infrastructure Reports
    {"key": "asset_inventory_report", "name": "Asset Inventory Report", "category": "infrastructure", "icon": "Database", "description": "Complete asset inventory with classification"},
    {"key": "kubernetes_security_report", "name": "Kubernetes Security Report", "category": "infrastructure", "icon": "Activity", "description": "K8s cluster security assessment"},
    {"key": "container_image_report", "name": "Container Image Report", "category": "infrastructure", "icon": "Box", "description": "Container image security scan results"},
    {"key": "cloud_security_report", "name": "Cloud Security Report", "category": "infrastructure", "icon": "Cloud", "description": "Cloud infrastructure security assessment"},

    # Compliance Reports
    {"key": "compliance_report", "name": "Compliance Report", "category": "compliance", "icon": "CheckSquare", "description": "Compliance status across frameworks"},
    {"key": "policy_compliance_report", "name": "Policy Compliance Report", "category": "compliance", "icon": "FileText", "description": "Security policy adherence report"},
    {"key": "license_compliance_report", "name": "License Compliance Report", "category": "compliance", "icon": "BookOpen", "description": "Software license compliance audit"},

    # Operational Reports
    {"key": "exception_report", "name": "Exception Report", "category": "operational", "icon": "FileText", "description": "Security exceptions with approval status"},
    {"key": "remediation_progress_report", "name": "Remediation Progress Report", "category": "operational", "icon": "Wrench", "description": "Remediation progress and MTTR metrics"},
    {"key": "sbom_report", "name": "SBOM Report", "category": "operational", "icon": "Layers", "description": "Software Bill of Materials report"},
    {"key": "audit_report", "name": "Audit Report", "category": "operational", "icon": "FileText", "description": "Comprehensive security audit report"},
]
