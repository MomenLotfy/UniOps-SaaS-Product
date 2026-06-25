from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Text, Integer, Float, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class K8sScan(BaseModel):
    """A point-in-time security scan of a Kubernetes cluster."""
    __tablename__ = "k8s_scans"

    tenant_id:      Mapped[str]            = mapped_column(String(36), nullable=False, index=True)
    cluster_id:     Mapped[str]            = mapped_column(String(36), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False, index=True)
    status:         Mapped[str]            = mapped_column(String(50),  nullable=False, default="pending")  # pending|running|completed|failed
    risk_score:     Mapped[float]          = mapped_column(Float, default=0.0)
    findings_count: Mapped[int]            = mapped_column(Integer, default=0)
    critical_count: Mapped[int]            = mapped_column(Integer, default=0)
    high_count:     Mapped[int]            = mapped_column(Integer, default=0)
    medium_count:   Mapped[int]            = mapped_column(Integer, default=0)
    low_count:      Mapped[int]            = mapped_column(Integer, default=0)
    info_count:     Mapped[int]            = mapped_column(Integer, default=0)
    scanners_run:   Mapped[list]           = mapped_column(JSON, default=list)  # ["native","kubescape","kube-bench","kube-hunter"]
    error_message:  Mapped[str | None]     = mapped_column(Text)
    started_at:     Mapped[datetime | None]= mapped_column(DateTime(timezone=True))
    completed_at:   Mapped[datetime | None]= mapped_column(DateTime(timezone=True))


class K8sFinding(BaseModel):
    """A single security finding from a Kubernetes cluster scan."""
    __tablename__ = "k8s_findings"

    tenant_id:     Mapped[str]         = mapped_column(String(36), nullable=False, index=True)
    cluster_id:    Mapped[str]         = mapped_column(String(36), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id:       Mapped[str | None]  = mapped_column(String(36), ForeignKey("k8s_scans.id", ondelete="SET NULL"), nullable=True, index=True)

    # Scanner that produced this finding
    scanner:       Mapped[str]         = mapped_column(String(50),  nullable=False, default="native")
    # Category: privileged_containers | rbac | exposed_services | network_policy | secrets | cis_benchmark | runtime
    category:      Mapped[str]         = mapped_column(String(100), nullable=False, index=True)
    severity:      Mapped[str]         = mapped_column(String(50),  nullable=False, default="medium", index=True)  # critical|high|medium|low|info

    title:         Mapped[str]         = mapped_column(String(500), nullable=False)
    description:   Mapped[str | None]  = mapped_column(Text)
    remediation:   Mapped[str | None]  = mapped_column(Text)
    references:    Mapped[list]        = mapped_column(JSON, default=list)

    # Affected Kubernetes resource
    resource_kind: Mapped[str | None]  = mapped_column(String(100))   # Pod|Deployment|ClusterRoleBinding|Service|…
    resource_name: Mapped[str | None]  = mapped_column(String(255))
    namespace:     Mapped[str | None]  = mapped_column(String(255))
    context:       Mapped[dict]        = mapped_column(JSON, default=dict)   # extra key/value context

    # Benchmark mapping
    cis_control:   Mapped[str | None]  = mapped_column(String(50))    # e.g. "1.2.1"
    framework:     Mapped[str | None]  = mapped_column(String(50))    # NSA | MITRE | CIS

    # Lifecycle
    status:        Mapped[str]         = mapped_column(String(50), nullable=False, default="open", index=True)  # open|resolved|suppressed
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suppressed:    Mapped[bool]        = mapped_column(Boolean, default=False)
