"""Compliance Check model.

This module provides the ComplianceCheck class used by the governance
overview service. The base Compliance model tracks framework-level scores;
ComplianceCheck records individual control evaluations (passed/failed/...)
across frameworks.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, JSON, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ComplianceCheck(BaseModel):
    """A single compliance control check result.

    One row per (framework, control) evaluation. Used by the governance
    compliance widget to surface category-level pass/fail breakdowns.
    """
    __tablename__ = "compliance_checks"

    tenant_id:    Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    framework:    Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    control_id:   Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title:        Mapped[str] = mapped_column(String(500), nullable=False)
    description:  Mapped[str | None] = mapped_column(Text)
    category:     Mapped[str | None] = mapped_column(String(100), index=True)
    severity:     Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    status:       Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    resource_id:  Mapped[str | None] = mapped_column(String(36), index=True)

    # Audit
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_check:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence:     Mapped[dict] = mapped_column(JSON, default=dict)
    remediation:  Mapped[str | None] = mapped_column(Text)
    score:        Mapped[int | None] = mapped_column(Integer, nullable=True)


__all__ = ["ComplianceCheck"]
