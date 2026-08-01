from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class HealthIndicator(BaseModel):
    resource_type: str
    total: int = 0
    healthy: int = 0
    warning: int = 0
    critical: int = 0
    unknown: int = 0


class RiskDistribution(BaseModel):
    by_severity: dict[str, int]
    by_repository: dict[str, int]
    by_business_unit: dict[str, int]
    by_team: dict[str, int]
    by_environment: dict[str, int]
    by_cloud_provider: dict[str, int]
    trend: list[dict]


class OwnershipSummary(BaseModel):
    total_owned: int
    teams_responsible: int
    departments_responsible: int
    owners: list[dict]


class SLASummary(BaseModel):
    total_sla: int
    compliant: int
    breached: int
    at_risk: int
    compliance_rate: float
    avg_response_time_hours: float


class RemediationOverview(BaseModel):
    total_open: int
    total_resolved: int
    avg_mttr_hours: float
    by_severity: dict[str, int]
    by_resource_type: dict[str, int]
    trends: list[dict]


class ComplianceOverview(BaseModel):
    total_checks: int
    passed: int
    failed: int
    passed_rate: float
    by_category: dict[str, int]
    by_standard: dict[str, int]


class PolicyOverview(BaseModel):
    total_policies: int
    active: int
    violated: int
    by_category: dict[str, int]
    by_status: dict[str, int]


class ThreatIntelligence(BaseModel):
    total_threats: int
    open_threats: int
    critical_threats: int
    by_severity: dict[str, int]
    by_source: dict[str, int]
    top_threats: list[dict]


class ExecutiveTimeline(BaseModel):
    recent_events: list[dict]
    upcoming_tasks: list[dict]
    alerts: list[dict]


class BusinessImpact(BaseModel):
    high_risk_business_units: list[dict]
    critical_applications: list[dict]
    service_affected_count: int
    estimated_impact_score: float


class GovernanceSummary(BaseModel):
    overall_security_score: float
    governance_score: float
    compliance_percentage: float
    risk_score: float
    open_findings: int
    critical_findings: int
    breached_slas: int
    open_exceptions: int
    remediation_progress_percentage: float
    policy_violations: int
    protected_assets_percentage: float
    repositories_covered_percentage: float
    average_mttr: float


class GovernanceOverviewResponse(BaseModel):
    summary: GovernanceSummary
    health_indicators: list[HealthIndicator]
    risk_distribution: RiskDistribution
    ownership_summary: OwnershipSummary
    sla_summary: SLASummary
    remediation_overview: RemediationOverview
    compliance_overview: ComplianceOverview
    policy_overview: PolicyOverview
    threat_intelligence: ThreatIntelligence
    executive_timeline: ExecutiveTimeline
    business_impact: BusinessImpact


class GovernanceExportFilter(BaseModel):
    date_range: str = Field(default="last_30_days")
    include_charts: bool = Field(default=True)
    format: str = Field(default="json")
