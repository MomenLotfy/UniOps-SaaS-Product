"""
Ownership Management Schemas
=============================

Pydantic schemas for ownership API requests and responses.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# ============================================
# Request Schemas
# ============================================

class OwnershipAssignRequest(BaseModel):
    """Request to assign ownership to an entity."""
    entity_type: str = Field(..., description="Type of entity (repository, threat, etc.)")
    entity_id: str = Field(..., description="ID of the entity")
    owner: Optional[str] = Field(None, description="Primary owner (email or name)")
    owner_type: Optional[str] = Field("user", description="Type of owner (user, team, etc.)")
    team: Optional[str] = Field(None, description="Team responsible")
    department: Optional[str] = Field(None, description="Department responsible")
    business_unit: Optional[str] = Field(None, description="Business unit responsible")
    backup_owner: Optional[str] = Field(None, description="Secondary/backup owner")
    escalation_chain: Optional[List[str]] = Field(None, description="List of escalation contacts")
    business_criticality: Optional[str] = Field("standard", description="Criticality level (critical, high, medium, low)")
    environment: Optional[str] = Field("unknown", description="Environment (production, staging, development, testing)")
    risk_level: Optional[str] = Field("medium", description="Risk level (critical, high, medium, low)")
    cloud_provider: Optional[str] = Field(None, description="Cloud provider (aws, azure, gcp)")
    cloud_account_id: Optional[str] = Field(None, description="Cloud account ID")
    cluster_name: Optional[str] = Field(None, description="Kubernetes cluster name")
    namespace: Optional[str] = Field(None, description="Kubernetes namespace")
    region: Optional[str] = Field(None, description="Region/zone")


class OwnershipBulkAssignRequest(BaseModel):
    """Request for bulk ownership assignment."""
    entity_type: str = Field(..., description="Type of entities to update")
    entity_ids: List[str] = Field(..., min_items=1, description="List of entity IDs")
    owner: Optional[str] = Field(None, description="Primary owner")
    owner_type: Optional[str] = Field("user", description="Type of owner")
    team: Optional[str] = Field(None, description="Team")
    department: Optional[str] = Field(None, description="Department")
    business_unit: Optional[str] = Field(None, description="Business unit")
    business_criticality: Optional[str] = Field(None, description="Criticality level")
    environment: Optional[str] = Field(None, description="Environment")
    risk_level: Optional[str] = Field(None, description="Risk level")


class OwnershipImportRequest(BaseModel):
    """Request for importing ownership mappings from CSV."""
    content: str = Field(..., description="CSV content")
    mapping_type: str = Field("overwrite", description="How to handle existing: overwrite, merge, skip_existing")


class OwnershipExportFilter(BaseModel):
    """Filter for exporting ownership data."""
    entity_types: Optional[List[str]] = Field(None, description="Filter by resource types")
    owner: Optional[str] = Field(None, description="Filter by owner")
    team: Optional[str] = Field(None, description="Filter by team")
    department: Optional[str] = Field(None, description="Filter by department")
    environment: Optional[str] = Field(None, description="Filter by environment")
    cloud_provider: Optional[str] = Field(None, description="Filter by cloud provider")
    include_audit_history: bool = Field(False, description="Include audit log in export")


# ============================================
# Response Schemas
# ============================================

class OwnershipMappingResponse(BaseModel):
    """Single ownership mapping response."""
    id: str
    tenant_id: str
    entity_type: str
    entity_id: str
    owner: Optional[str]
    owner_type: str
    team: Optional[str]
    department: Optional[str]
    business_unit: Optional[str]
    backup_owner: Optional[str]
    escalation_chain: List[str]
    business_criticality: str
    environment: str
    region: Optional[str]
    risk_level: str
    sla_status: str
    cloud_provider: Optional[str]
    cloud_account_id: Optional[str]
    cluster_name: Optional[str]
    namespace: Optional[str]
    last_updated: Optional[datetime]
    is_assigned: bool
    assignment_method: str
    entity_name: Optional[str] = None  # Optional entity display name

    model_config = ConfigDict(from_attributes=True)


class OwnershipSummaryResponse(BaseModel):
    """Summary statistics for ownership."""
    total_resources: int
    owned_resources: int
    unassigned_resources: int
    teams: int
    departments: int
    security_owners: int
    repositories_covered: int
    clusters_covered: int
    sla_violations: int
    ownership_coverage_percent: float
    by_resource_type: Dict[str, int] = Field(default_factory=dict)
    by_environment: Dict[str, int] = Field(default_factory=dict)
    by_cloud_provider: Dict[str, int] = Field(default_factory=dict)


class OwnershipCoverageResponse(BaseModel):
    """Coverage data for charts."""
    total: int
    owned: int
    unassigned: int
    coverage_percent: float

    by_team: List[Dict[str, Any]] = Field(default_factory=list)
    by_department: List[Dict[str, Any]] = Field(default_factory=list)
    by_environment: List[Dict[str, Any]] = Field(default_factory=list)
    by_cloud_provider: List[Dict[str, Any]] = Field(default_factory=list)
    by_resource_type: List[Dict[str, Any]] = Field(default_factory=list)


class OwnerProfileResponse(BaseModel):
    """Owner profile with assigned resources."""
    owner: str
    owner_type: str
    email: Optional[str] = None
    team: Optional[str] = None
    department: Optional[str] = None
    business_unit: Optional[str] = None

    # Resource counts
    total_resources: int
    total_vulnerabilities: int
    total_threats: int
    total_remediations: int
    compliance_violations: int

    # Performance metrics
    avg_mttr_hours: Optional[float]
    sla_compliance_rate: Optional[float]

    # Risk distribution
    critical_risk_count: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int

    # Ownership breakdown
    repository_ownership: List[Dict[str, Any]]
    infrastructure_ownership: List[Dict[str, Any]]
    application_ownership: List[Dict[str, Any]]

    # SLA performance
    sla_by_month: List[Dict[str, Any]]
    overdue_tasks: int


class AuditLogResponse(BaseModel):
    """Audit log entry."""
    id: str
    tenant_id: str
    entity_type: str
    entity_id: str
    entity_name: Optional[str]
    prev_owner: Optional[str]
    prev_team: Optional[str]
    prev_department: Optional[str]
    new_owner: Optional[str]
    new_team: Optional[str]
    new_department: Optional[str]
    changed_by: str
    change_type: str
    reason: Optional[str]
    changed_at: datetime


class OwnershipImportResult(BaseModel):
    """Result of ownership import operation."""
    total_processed: int
    success: int
    failures: int
    errors: List[Dict[str, Any]]


# ============================================
# API Response Wrappers
# ============================================

from app.schemas.common import APIResponse, PaginatedResponse


class OwnershipListResponse(APIResponse[OwnershipMappingResponse]):
    data: List[OwnershipMappingResponse]


class OwnershipSummaryResponseWrapper(APIResponse[OwnershipSummaryResponse]):
    pass


class OwnershipCoverageResponseWrapper(APIResponse[OwnershipCoverageResponse]):
    pass


class OwnerProfileResponseWrapper(APIResponse[OwnerProfileResponse]):
    pass


class AuditLogPaginatedResponse(PaginatedResponse[AuditLogResponse]):
    pass


class OwnershipImportResponse(APIResponse[OwnershipImportResult]):
    pass
