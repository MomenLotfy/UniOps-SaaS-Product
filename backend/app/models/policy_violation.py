from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class PolicyViolation(BaseModel):
    """
    A single policy-rule violation found during a scan.
    Created by PolicyEvaluator when a finding breaks an active policy.
    """
    __tablename__ = "policy_violations"

    tenant_id:       Mapped[str]        = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    policy_id:       Mapped[str]        = mapped_column(String(36), ForeignKey("security_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id:         Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # What entity was in violation
    entity_type:     Mapped[str]        = mapped_column(String(50),  nullable=False)   # threat | vulnerability | repository | asset
    entity_id:       Mapped[str]        = mapped_column(String(36),  nullable=False, index=True)
    entity_title:    Mapped[str | None] = mapped_column(String(500))

    # Which rule was violated
    rule_key:        Mapped[str]        = mapped_column(String(100), nullable=False)   # e.g. no_secrets | block_critical_cve
    rule_description: Mapped[str | None] = mapped_column(Text)

    # Severity of the violation (copied from policy or finding)
    severity:        Mapped[str]        = mapped_column(String(50), default="high")

    # Enforcement action taken
    enforcement_mode: Mapped[str]       = mapped_column(String(50), default="audit")  # audit | enforce
    was_blocked:     Mapped[bool]       = mapped_column(Boolean, default=False)

    # Active exception covering this violation?
    exception_id:    Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_suppressed:   Mapped[bool]       = mapped_column(Boolean, default=False)

    # Raw context for debugging
    context:         Mapped[dict]       = mapped_column(JSON, default=dict)

    # Resolved when the underlying finding is fixed
    resolved_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status:          Mapped[str]        = mapped_column(String(50), default="open", index=True)  # open | resolved | suppressed
