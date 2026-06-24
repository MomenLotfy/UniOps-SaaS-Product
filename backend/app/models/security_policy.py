from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class SecurityPolicy(BaseModel):
    __tablename__ = "security_policies"

    tenant_id:        Mapped[str]           = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    name:             Mapped[str]           = mapped_column(String(255), nullable=False)
    description:      Mapped[str | None]    = mapped_column(Text)
    category:         Mapped[str]           = mapped_column(String(100), nullable=False)
    severity:         Mapped[str]           = mapped_column(String(50), default="medium")
    status:           Mapped[str]           = mapped_column(String(50), default="active")
    enforcement:      Mapped[str]           = mapped_column(String(50), default="advisory")
    scope:            Mapped[dict]          = mapped_column(JSON, default=dict)
    rules:            Mapped[list]          = mapped_column(JSON, default=list)
    exceptions_count: Mapped[int]           = mapped_column(default=0)
    violations_count: Mapped[int]           = mapped_column(default=0)
    created_by:       Mapped[str | None]    = mapped_column(String(36))
    updated_by:       Mapped[str | None]    = mapped_column(String(36))
    effective_date:   Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    review_date:      Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    frameworks:       Mapped[list]          = mapped_column(JSON, default=list)
    tags:             Mapped[dict]          = mapped_column(JSON, default=dict)
