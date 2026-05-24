from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Alert(BaseModel):
    __tablename__ = "alerts"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="active")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    resource: Mapped[str | None] = mapped_column(String(500))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
