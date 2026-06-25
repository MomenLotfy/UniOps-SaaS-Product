from __future__ import annotations
from datetime import datetime, timezone, timedelta
from sqlalchemy import String, ForeignKey, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

# SLA windows in hours
SLA_HOURS: dict[str, int] = {
    "critical": 24,
    "high":     7 * 24,
    "medium":   30 * 24,
    "low":      90 * 24,
}


def sla_due_at(severity: str, detected_at: datetime) -> datetime:
    hours = SLA_HOURS.get(severity.lower(), 30 * 24)
    return detected_at + timedelta(hours=hours)


class FindingSLA(BaseModel):
    """
    SLA record for a single security finding (threat or vulnerability).
    One row per finding — upserted on each scan.
    """
    __tablename__ = "finding_slas"

    tenant_id:    Mapped[str]  = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    entity_type:  Mapped[str]  = mapped_column(String(50),  nullable=False, index=True)  # threat | vulnerability
    entity_id:    Mapped[str]  = mapped_column(String(36),  nullable=False, index=True)

    severity:     Mapped[str]  = mapped_column(String(50),  nullable=False)
    title:        Mapped[str | None] = mapped_column(String(500))

    detected_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sla_due_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sla_hours:    Mapped[int]      = mapped_column(Integer, nullable=False)

    # resolved_at is set when the finding is closed; NULL = still open
    resolved_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Computed flags — refreshed by scheduler
    is_overdue:   Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_breached:  Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # once overdue, always breached

    # Owner / team copied from the finding at snapshot time
    owner:      Mapped[str | None] = mapped_column(String(255))
    team:       Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(255))

    # Status: open | resolved | breached | suppressed
    status:     Mapped[str] = mapped_column(String(50), default="open", nullable=False, index=True)
