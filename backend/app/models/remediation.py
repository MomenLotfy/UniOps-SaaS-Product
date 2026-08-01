"""Remediation Task model.

This module provides the RemediationTask class used by the governance
overview service and the reports service. It tracks remediation progress
and MTTR (mean time to remediate) per finding.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Integer, Float, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RemediationTask(BaseModel):
    """A remediation task tied to a single security finding.

    One row per remediation. Used by:
    - governance overview dashboard
    - reports (remediation progress template)
    - remediation endpoints
    """
    __tablename__ = "remediation_tasks"

    tenant_id:    Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    # Link to the original finding
    entity_type:  Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # threat | vulnerability
    entity_id:    Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Task metadata
    title:        Mapped[str] = mapped_column(String(500), nullable=False)
    description:  Mapped[str | None] = mapped_column(Text)
    severity:     Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    status:       Mapped[str] = mapped_column(String(50), default="open", nullable=False, index=True)
    priority:     Mapped[str] = mapped_column(String(50), default="normal", nullable=False)

    # Assignment
    owner:        Mapped[str | None] = mapped_column(String(255), index=True)
    team:         Mapped[str | None] = mapped_column(String(255))
    assigned_to:  Mapped[str | None] = mapped_column(String(36))

    # Lifecycle
    detected_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # MTTR tracking
    mttr_hours:   Mapped[float | None] = mapped_column(Float, nullable=True)
    sla_breached: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Audit
    extra:        Mapped[dict] = mapped_column(JSON, default=dict)
    created_by:   Mapped[str | None] = mapped_column(String(36))


__all__ = ["RemediationTask"]
