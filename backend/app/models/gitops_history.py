from datetime import datetime
from sqlalchemy import String, ForeignKey, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class GitOpsHistory(BaseModel):
    __tablename__ = "gitops_history"

    tenant_id:   Mapped[str]            = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    app_id:      Mapped[str]            = mapped_column(String(36), ForeignKey("gitops_apps.id"), nullable=False, index=True)
    revision:    Mapped[str]            = mapped_column(String(255))
    short_sha:   Mapped[str | None]     = mapped_column(String(12))
    author:      Mapped[str | None]     = mapped_column(String(255))
    message:     Mapped[str | None]     = mapped_column(Text)
    deployed_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True))
    deployed_by: Mapped[str | None]     = mapped_column(String(255))
    status:      Mapped[str]            = mapped_column(String(20), default="Succeeded")  # Succeeded|Failed|Running
    source_type: Mapped[str]            = mapped_column(String(20), default="sync")       # sync|rollback|auto
