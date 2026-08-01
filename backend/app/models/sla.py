"""SLA models.

This module provides the SLA and SLAMonitoring classes used by the
governance overview service. They share the finding_sla table (FindingSLA)
and the FindingSLA model in finding_sla.py is the canonical record; this
module adds lightweight aliases plus the SLAMonitoring aggregate so the
governance dashboard can compute summary statistics.

Why this exists: the governance overview service imports
`SLA, SLAMonitoring` from `app.models.sla`. The actual records live in
`finding_slas` (FindingSLA). Without these aliases, governance fails to
import and the entire API fails to boot.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.finding_sla import FindingSLA  # re-export canonical table


class SLA(BaseModel):
    """Per-severity SLA policy used by the governance dashboard.

    The actual per-finding SLA records live in `finding_slas` (FindingSLA).
    This row lets ops define their own severity-to-hours windows and have
    them surface in the SLA summary widget.
    """
    __tablename__ = "sla_policies"

    tenant_id:    Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    severity:     Mapped[str] = mapped_column(String(50), nullable=False, unique=False)
    sla_hours:    Mapped[int] = mapped_column(Integer, nullable=False)
    description:  Mapped[str | None] = mapped_column(String(500))
    is_active:    Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by:   Mapped[str | None] = mapped_column(String(36))


class SLAMonitoring(BaseModel):
    """Snapshot of a finding's SLA status at a point in time.

    This is a denormalized aggregate table that powers the governance
    SLA summary without re-computing from FindingSLA on every read.
    """
    __tablename__ = "sla_monitoring"

    tenant_id:    Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    finding_id:   Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_type:  Mapped[str] = mapped_column(String(50), nullable=False)
    severity:     Mapped[str] = mapped_column(String(50), nullable=False)
    sla_due_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status:       Mapped[str] = mapped_column(String(50), default="compliant", nullable=False, index=True)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["SLA", "SLAMonitoring", "FindingSLA"]
