from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class GitOpsApp(BaseModel):
    __tablename__ = "gitops_apps"

    tenant_id:       Mapped[str]            = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    cluster_id:      Mapped[str | None]     = mapped_column(String(36), index=True)
    # App identity
    name:            Mapped[str]            = mapped_column(String(255), nullable=False)
    project:         Mapped[str]            = mapped_column(String(255), default="default")
    namespace:       Mapped[str]            = mapped_column(String(255), default="default")
    cluster_server:  Mapped[str | None]     = mapped_column(String(512))   # ArgoCD cluster URL
    # Source
    source_type:     Mapped[str]            = mapped_column(String(20), default="git")  # git | helm | kustomize
    repo_url:        Mapped[str | None]     = mapped_column(Text)
    target_revision: Mapped[str]            = mapped_column(String(255), default="HEAD")
    path:            Mapped[str | None]     = mapped_column(String(512))
    helm_chart:      Mapped[str | None]     = mapped_column(String(255))
    helm_values:     Mapped[dict]           = mapped_column(JSON, default=dict)
    # Sync status
    health_status:   Mapped[str]            = mapped_column(String(30), default="Unknown")   # Healthy|Degraded|Progressing|Missing|Suspended|Unknown
    sync_status:     Mapped[str]            = mapped_column(String(20), default="Unknown")   # Synced|OutOfSync|Unknown
    sync_message:    Mapped[str | None]     = mapped_column(Text)
    last_synced_at:  Mapped[datetime | None]= mapped_column(DateTime(timezone=True))
    current_revision:Mapped[str | None]     = mapped_column(String(255))
    # ArgoCD link
    argocd_app_name: Mapped[str | None]     = mapped_column(String(255))
    argocd_server:   Mapped[str | None]     = mapped_column(String(512))
    # Resources summary
    resource_summary:Mapped[dict]           = mapped_column(JSON, default=dict)
