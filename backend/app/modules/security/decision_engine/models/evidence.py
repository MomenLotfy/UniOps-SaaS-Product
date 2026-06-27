from __future__ import annotations
from typing import Optional
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import DecisionBase

class DecisionReason(DecisionBase):
    """
    Justification for why a specific decision was reached.
    """
    __tablename__ = "security_decision_reasons"

    decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decisions.id"), index=True)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. 'SENSITIVE_DATA_FOUND'
    description: Mapped[str] = mapped_column(String(1000), nullable=False)

    decision: Mapped["Decision"] = relationship(back_populates="reasons")
    evidence: Mapped[List["DecisionEvidence"]] = relationship(back_populates="reason")

class DecisionEvidence(DecisionBase):
    """
    Supporting data or logs that justify a DecisionReason.
    """
    __tablename__ = "security_decision_evidence"

    reason_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decision_reasons.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. 'SCA_LOG', 'K8S_MANIFEST'
    evidence_value: Mapped[str] = mapped_column(String(2000), nullable=False)

    reason: Mapped["DecisionReason"] = relationship(back_populates="evidence")

class DecisionConstraint(DecisionBase):
    """
    Pre-conditions that must be met for a decision to be valid.
    """
    __tablename__ = "security_decision_constraints"

    decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decisions.id"), index=True)
    constraint_type: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. 'OWNER_APPROVAL_REQUIRED'
    is_met: Mapped[bool] = mapped_column(String(10), default="false") # Stored as string for simplicity or use Boolean

    decision: Mapped["Decision"] = relationship(back_populates="constraints")
