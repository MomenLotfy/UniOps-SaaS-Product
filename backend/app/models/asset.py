from __future__ import annotations
"""
Asset Inventory Models
======================
`Asset`              — a discovered resource (repo, EC2, S3, pod, …)
`AssetRelationship`  — directed edge between two assets (pod→namespace, etc.)

Upsert key: (tenant_id, source, external_id)  — guarantees idempotent syncs.
"""
from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Boolean, DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


ASSET_TYPES = {
    "github_repo", "gitlab_repo", "bitbucket_repo", "azure_devops_repo",
    "aws_ec2", "aws_s3", "aws_iam_user", "aws_iam_role", "aws_rds",
    "aws_ecr_repository", "aws_eks_cluster",
    "aws_cloudwatch_alarm", "aws_cloudwatch_log_group",
    "gcp_storage_bucket", "azure_blob_container",
    "docker_image",
    "k8s_cluster", "k8s_namespace", "k8s_pod",
}

RELATIONSHIP_TYPES = {
    "contains",       # cluster contains namespace; namespace contains pod
    "runs_on",        # pod runs docker_image
    "hosted_in",      # ec2 hosted_in region/vpc
    "depends_on",     # repo depends_on another repo / package
    "scanned_by",     # asset scanned_by a scan
    "belongs_to",     # iam_user belongs_to account
}


class Asset(BaseModel):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source", "external_id",
            name="uq_asset_tenant_source_external",
        ),
    )

    tenant_id:       Mapped[str]             = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    integration_id:  Mapped[str | None]      = mapped_column(String(36), ForeignKey("integrations.id"), nullable=True)

    name:            Mapped[str]             = mapped_column(String(500), nullable=False)
    type:            Mapped[str]             = mapped_column(String(50),  nullable=False, index=True)
    source:          Mapped[str]             = mapped_column(String(50),  nullable=False, index=True)
    external_id:     Mapped[str]             = mapped_column(String(500), nullable=False)

    environment:     Mapped[str]             = mapped_column(String(50),  default="unknown")
    status:          Mapped[str]             = mapped_column(String(50),  default="active", index=True)
    risk_level:      Mapped[str]             = mapped_column(String(20),  default="none",   index=True)

    owner:           Mapped[str | None]      = mapped_column(String(255))
    team:            Mapped[str | None]      = mapped_column(String(255))
    description:     Mapped[str | None]      = mapped_column(Text)

    region:          Mapped[str | None]      = mapped_column(String(100))
    account_id:      Mapped[str | None]      = mapped_column(String(100))
    namespace:       Mapped[str | None]      = mapped_column(String(255))
    cluster:         Mapped[str | None]      = mapped_column(String(255))
    url:             Mapped[str | None]      = mapped_column(Text)

    is_critical:     Mapped[bool]            = mapped_column(Boolean, default=False)
    open_findings:   Mapped[int]             = mapped_column(Integer, default=0)

    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tags:            Mapped[dict]            = mapped_column(JSON, default=dict)
    meta:            Mapped[dict]            = mapped_column(JSON, default=dict)

    def to_dict(self) -> dict:
        result = {}
        for col in self.__table__.columns:
            val = getattr(self, col.name)
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            result[col.name] = val
        return result


class AssetRelationship(BaseModel):
    __tablename__ = "asset_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_asset_id", "target_asset_id", "relationship_type",
            name="uq_asset_rel_unique",
        ),
    )

    tenant_id:         Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    source_asset_id:   Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"),  nullable=False, index=True)
    target_asset_id:   Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"),  nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    meta:              Mapped[dict] = mapped_column(JSON, default=dict)

    def to_dict(self) -> dict:
        result = {}
        for col in self.__table__.columns:
            val = getattr(self, col.name)
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            result[col.name] = val
        return result
