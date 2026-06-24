from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class SecurityException(BaseModel):
    __tablename__ = "security_exceptions"

    tenant_id:      Mapped[str]           = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    policy_id:      Mapped[str | None]    = mapped_column(String(36), nullable=True, index=True)
    finding_id:     Mapped[str | None]    = mapped_column(String(36), nullable=True)
    finding_type:   Mapped[str | None]    = mapped_column(String(50))
    title:          Mapped[str]           = mapped_column(String(500), nullable=False)
    justification:  Mapped[str]           = mapped_column(Text, nullable=False)
    risk_acceptance: Mapped[str]          = mapped_column(Text)
    status:         Mapped[str]           = mapped_column(String(50), default="pending")
    exception_type: Mapped[str]           = mapped_column(String(50), default="temporary")
    requested_by:   Mapped[str]           = mapped_column(String(36), nullable=False, index=True)
    approved_by:    Mapped[str | None]    = mapped_column(String(36))
    rejected_by:    Mapped[str | None]    = mapped_column(String(36))
    reviewer_note:  Mapped[str | None]    = mapped_column(Text)
    expires_at:     Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    reviewed_at:    Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    scope:          Mapped[dict]          = mapped_column(JSON, default=dict)
    tags:           Mapped[dict]          = mapped_column(JSON, default=dict)
