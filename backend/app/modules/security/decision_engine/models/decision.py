from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, ForeignKey, JSON, DateTime, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import DecisionBase
from ..constants import DecisionState

class Decision(DecisionBase):
    """
    The root entity representing a security remediation decision.
    """
    __tablename__ = "security_decisions"

    # Decision specific fields
    status: Mapped[DecisionState] = mapped_column(Enum(DecisionState), default=DecisionState.CREATED)
    final_result: Mapped[Optional[str]] = mapped_column(String(100)) # e.g. 'PATCH', 'MITIGATE', 'IGNORE'
    context_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decision_contexts.id"), index=True)

    # Relationships
    # Sprint 2 R17: ``lazy="selectin"`` so child collections are auto-loaded
    # after the parent — eliminates MissingGreenlet on detached sessions.
    context: Mapped["DecisionContext"] = relationship(lazy="selectin")
    plan: Mapped["DecisionPlan"] = relationship(back_populates="decision", lazy="selectin")
    history: Mapped[List["DecisionHistory"]] = relationship(back_populates="decision", lazy="selectin")
    versions: Mapped[List["DecisionVersion"]] = relationship(back_populates="decision", lazy="selectin")
    reasons: Mapped[List["DecisionReason"]] = relationship(back_populates="decision", lazy="selectin")
    constraints: Mapped[List["DecisionConstraint"]] = relationship(back_populates="decision", lazy="selectin")
    policy_ref: Mapped[Optional["DecisionPolicyReference"]] = relationship(back_populates="decision", lazy="selectin")

class DecisionHistory(DecisionBase):
    """
    Audit trail of state transitions for a decision.
    """
    __tablename__ = "security_decision_history"

    decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decisions.id"), index=True)
    from_state: Mapped[DecisionState] = mapped_column(Enum(DecisionState), nullable=True)
    to_state: Mapped[DecisionState] = mapped_column(Enum(DecisionState), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100)) # system | user_id
    change_reason: Mapped[Optional[str]] = mapped_column(String(1000))

    decision: Mapped["Decision"] = relationship(back_populates="history")

class DecisionVersion(DecisionBase):
    """
    Snapshot of a decision at a specific version for historical analysis.
    """
    __tablename__ = "security_decision_versions"

    decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decisions.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False) # Full serialized state of decision and plan

    decision: Mapped["Decision"] = relationship(back_populates="versions")
