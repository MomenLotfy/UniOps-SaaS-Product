from __future__ import annotations
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import DecisionBase

class DecisionPolicyReference(DecisionBase):
    """
    Link to the specific policy version that triggered the decision.
    """
    __tablename__ = "security_decision_policies"

    decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decisions.id"), index=True)
    policy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)

    decision: Mapped["Decision"] = relationship(back_populates="policy_ref")
