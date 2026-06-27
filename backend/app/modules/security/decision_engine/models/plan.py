from __future__ import annotations
from typing import Optional, List
from sqlalchemy import String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import DecisionBase

class DecisionPlan(DecisionBase):
    """
    The execution blueprint for achieving the remediation decision.
    """
    __tablename__ = "security_decision_plans"

    decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decisions.id"), index=True)
    execution_order: Mapped[int] = mapped_column(Integer, default=1)

    decision: Mapped["Decision"] = relationship(back_populates="plan")
    steps: Mapped[List["DecisionStep"]] = relationship(back_populates="plan")

class DecisionStep(DecisionBase):
    """
    Atomic operation within a decision plan.
    """
    __tablename__ = "security_decision_steps"

    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decision_plans.id"), index=True)
    step_type: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. 'VERIFY_DEPENDENCY', 'CHECK_VERSION'
    result: Mapped[Optional[str]] = mapped_column(String(1000)) # Outcome of the step execution

    plan: Mapped["DecisionPlan"] = relationship(back_populates="steps")
