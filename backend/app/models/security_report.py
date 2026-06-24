from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class SecurityReport(BaseModel):
    __tablename__ = "security_reports"

    tenant_id:    Mapped[str]           = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    name:         Mapped[str]           = mapped_column(String(255), nullable=False)
    description:  Mapped[str | None]    = mapped_column(Text)
    report_type:  Mapped[str]           = mapped_column(String(100), nullable=False)
    status:       Mapped[str]           = mapped_column(String(50), default="generating")
    format:       Mapped[str]           = mapped_column(String(20), default="json")
    generated_by: Mapped[str]           = mapped_column(String(36), nullable=False, index=True)
    parameters:   Mapped[dict]          = mapped_column(JSON, default=dict)
    summary:      Mapped[dict]          = mapped_column(JSON, default=dict)
    findings:     Mapped[dict]          = mapped_column(JSON, default=dict)
    period_start: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    period_end:   Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    error:        Mapped[str | None]    = mapped_column(Text)
