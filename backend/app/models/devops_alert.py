from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class DevOpsAlert(BaseModel):
    __tablename__ = "devops_alerts"

    tenant_id:   Mapped[str]            = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    cluster_id:  Mapped[str | None]     = mapped_column(String(36), index=True)
    namespace:   Mapped[str | None]     = mapped_column(String(255))
    name:        Mapped[str]            = mapped_column(String(255), nullable=False)
    severity:    Mapped[str]            = mapped_column(String(20),  nullable=False, default="warning")  # critical|warning|info
    type:        Mapped[str]            = mapped_column(String(100), nullable=False)   # CrashLoopBackOff|HighCPU|...
    resource:    Mapped[str | None]     = mapped_column(String(255))    # pod/deployment name
    message:     Mapped[str]            = mapped_column(Text, nullable=False)
    status:      Mapped[str]            = mapped_column(String(20),  nullable=False, default="firing")  # firing|acknowledged|muted|resolved
    muted_until: Mapped[datetime | None]= mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None]= mapped_column(DateTime(timezone=True))
    labels:      Mapped[dict]           = mapped_column(JSON, default=dict)
    annotations: Mapped[dict]           = mapped_column(JSON, default=dict)
    notified:    Mapped[bool]           = mapped_column(Boolean, default=False)
    fired_at:    Mapped[datetime | None]= mapped_column(DateTime(timezone=True))
