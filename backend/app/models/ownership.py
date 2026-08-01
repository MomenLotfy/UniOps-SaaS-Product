"""
Ownership Management Models
============================

Each entity that can be owned has an owner, team, and department field added directly.
This module provides the schema definitions and ownership mapping utilities.

Supported Owner Types:
- User (email format)
- Team
- Department
- Business Unit
- Service Owner
- Application Owner
- Security Owner
- Infrastructure Owner
- Platform Team

Supported Resource Types:
- Repository (Git repository)
- Organization
- Project
- Application
- Service
- Microservice
- Container Image
- Asset
- Virtual Machine
- Cloud Account
- Kubernetes Cluster
- Namespace
- Deployment
- Pod
- Secret
- Database
- Storage Bucket
- Load Balancer
- Policy
- Compliance Control
- Exception
- Threat
- Vulnerability
- Remediation Task
- SBOM
"""

from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, DateTime, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


# Owner type constants
OWNER_TYPES = {
    "user",                      # Individual user email
    "team",                      # Team name
    "department",                # Department name
    "business_unit",             # Business unit
    "service_owner",            # Service owner
    "application_owner",        # Application owner
    "security_owner",           # Security team
    "infrastructure_owner",     # Infrastructure team
    "platform_team",            # Platform team
}

# Resource types with their display names
RESOURCE_TYPES = {
    "repository":            "Repository",
    "organization":          "Organization",
    "project":               "Project",
    "application":           "Application",
    "service":               "Service",
    "microservice":          "Microservice",
    "container_image":       "Container Image",
    "asset":                 "Asset",
    "virtual_machine":       "Virtual Machine",
    "cloud_account":         "Cloud Account",
    "kubernetes_cluster":    "Kubernetes Cluster",
    "namespace":             "Namespace",
    "deployment":            "Deployment",
    "pod":                   "Pod",
    "secret":                "Secret",
    "database":              "Database",
    "storage_bucket":        "Storage Bucket",
    "load_balancer":         "Load Balancer",
    "policy":                "Policy",
    "compliance_control":    "Compliance Control",
    "exception":             "Exception",
    "threat":                "Threat",
    "vulnerability":         "Vulnerability",
    "remediation_task":      "Remediation Task",
    "sbom":                  "SBOM",
}


class OwnershipMapping(BaseModel):
    """
    Central ownership mapping table.
    Stores ownership information for any entity type.
    This provides a unified view of ownership across all resources.
    """
    __tablename__ = "ownership_mappings"

    tenant_id:     Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    # Entity reference
    entity_type:   Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # repository, threat, etc.
    entity_id:     Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Owner information
    owner:         Mapped[str | None] = mapped_column(String(255))  # Primary owner (email or name)
    owner_type:    Mapped[str] = mapped_column(String(50), default="user")  # user, team, department, etc.

    # Organization structure
    team:          Mapped[str | None] = mapped_column(String(255))
    department:    Mapped[str | None] = mapped_column(String(255))
    business_unit: Mapped[str | None] = mapped_column(String(255))

    # Escalation chain
    backup_owner:  Mapped[str | None] = mapped_column(String(255))
    escalation_chain: Mapped[list] = mapped_column(JSON, default=list)  # List of owner IDs

    # Business context
    business_criticality: Mapped[str] = mapped_column(String(50), default="standard")  # critical, high, medium, low
    environment:   Mapped[str] = mapped_column(String(50), default="unknown")  # production, staging, development, testing
    region:        Mapped[str | None] = mapped_column(String(100))  # For cloud resources

    # Risk and compliance
    risk_level:    Mapped[str] = mapped_column(String(20), default="medium")  # critical, high, medium, low, none
    sla_status:    Mapped[str] = mapped_column(String(50), default="compliant")  # compliant, at_risk, violation

    # Ownership metadata
    last_updated:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by:    Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))

    # Assignments tracking
    is_assigned:   Mapped[bool] = mapped_column(Boolean, default=False)
    assignment_method: Mapped[str] = mapped_column(String(50), default="manual")  # manual, auto, import, default

    # Cloud/provider specific
    cloud_provider: Mapped[str | None] = mapped_column(String(50))  # aws, azure, gcp, kubernetes
    cloud_account_id: Mapped[str | None] = mapped_column(String(100))
    cluster_name:   Mapped[str | None] = mapped_column(String(255))
    namespace:      Mapped[str | None] = mapped_column(String(255))

    # Audit
    assigned_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def to_dict(self) -> dict:
        result = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        if result.get("last_updated") and hasattr(result["last_updated"], "isoformat"):
            result["last_updated"] = result["last_updated"].isoformat()
        if result.get("assigned_at") and hasattr(result["assigned_at"], "isoformat"):
            result["assigned_at"] = result["assigned_at"].isoformat()
        if result.get("removed_at") and hasattr(result["removed_at"], "isoformat"):
            result["removed_at"] = result["removed_at"].isoformat()
        return result


class OwnershipAuditLog(BaseModel):
    """
    Audit log for ownership changes.
    Tracks who changed ownership, when, and why.
    """
    __tablename__ = "ownership_audit_logs"

    tenant_id:    Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    # Change details
    entity_type:  Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id:    Mapped[str] = mapped_column(String(36), nullable=False)
    entity_name:  Mapped[str | None] = mapped_column(String(500))

    # Ownership before/after
    prev_owner:   Mapped[str | None] = mapped_column(String(255))
    prev_team:    Mapped[str | None] = mapped_column(String(255))
    prev_dept:    Mapped[str | None] = mapped_column(String(255))

    new_owner:    Mapped[str | None] = mapped_column(String(255))
    new_team:     Mapped[str | None] = mapped_column(String(255))
    new_dept:     Mapped[str | None] = mapped_column(String(255))

    # Change metadata
    changed_by:   Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    change_type:  Mapped[str] = mapped_column(String(50), nullable=False)  # assign, update, remove, bulk
    reason:       Mapped[str | None] = mapped_column(Text)

    # Timestamp
    changed_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        result = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        if result.get("changed_at") and hasattr(result["changed_at"], "isoformat"):
            result["changed_at"] = result["changed_at"].isoformat()
        return result


class OwnershipDefault(BaseModel):
    """
    Default ownership rules for automatic assignment.
    When new resources are created, apply default ownership based on rules.
    """
    __tablename__ = "ownership_defaults"

    tenant_id:   Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    # Rule criteria
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # repository, asset, etc.
    environment:   Mapped[str | None] = mapped_column(String(50))  # production, staging, dev, null=all
    cloud_provider: Mapped[str | None] = mapped_column(String(50))  # aws, azure, gcp, k8s, null=all
    region:        Mapped[str | None] = mapped_column(String(100))  # null=all
    tag_key:       Mapped[str | None] = mapped_column(String(100))  # null=match all
    tag_value:     Mapped[str | None] = mapped_column(String(100))  # null=match all

    # Default ownership
    owner:         Mapped[str] = mapped_column(String(255))
    owner_type:    Mapped[str] = mapped_column(String(50), default="user")
    team:          Mapped[str | None] = mapped_column(String(255))
    department:    Mapped[str | None] = mapped_column(String(255))

    # Rule metadata
    is_active:     Mapped[bool] = mapped_column(Boolean, default=True)
    priority:      Mapped[int] = mapped_column(Integer, default=100)  # Lower = higher priority
    rule_name:     Mapped[str | None] = mapped_column(String(255))
    created_by:    Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
