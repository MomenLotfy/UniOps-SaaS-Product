from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from enum import Enum as PyEnum
from sqlalchemy import String, ForeignKey, JSON, DateTime, Integer, Boolean, Enum, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import DecisionBase

class PolicyStatus(str, PyEnum):
    """
    Lifecycle status of a security policy.
    """
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"

class DecisionPolicy(DecisionBase):
    """
    The root entity for organizational security policies used by the Decision Engine.
    """
    __tablename__ = "security_decision_policies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    category: Mapped[str] = mapped_column(String(100), index=True) # e.g. 'compliance', 'critical-infra'
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    status: Mapped[PolicyStatus] = mapped_column(Enum(PolicyStatus), default=PolicyStatus.DRAFT)

    # Scope definition: JSON containing {'type': 'repo|org|tenant', 'id': '...' }
    scope: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: {"type": "tenant", "id": None})

    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    versions: Mapped[List["PolicyVersion"]] = relationship(back_populates="policy")
    evaluations: Mapped[List["PolicyEvaluation"]] = relationship(back_populates="policy")
    history: Mapped[List["PolicyHistory"]] = relationship(back_populates="policy")

class PolicyVersion(DecisionBase):
    """
    Snapshot of a policy definition for version tracking and rollbacks.
    """
    __tablename__ = "security_decision_policy_versions"

    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decision_policies.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    policy: Mapped["DecisionPolicy"] = relationship(back_populates="versions")

class PolicyEvaluation(DecisionBase):
    """
    Audit of a specific policy resolution and application.
    """
    __tablename__ = "security_decision_policy_evaluations"

    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decision_policies.id"), index=True)
    decision_id: Mapped[str] = mapped_column(String(36), index=True)
    input_result: Mapped[str] = mapped_column(String(100))
    output_result: Mapped[str] = mapped_column(String(100))
    resolution_path: Mapped[str] = mapped_column(String(1000))

    policy: Mapped["DecisionPolicy"] = relationship(back_populates="evaluations")

class PolicyHistory(DecisionBase):
    """
    Audit trail of changes to a policy.
    """
    __tablename__ = "security_decision_policy_history"

    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decision_policies.id"), index=True)
    from_state: Mapped[Optional[str]] = mapped_column(String(100))
    to_state: Mapped[Optional[str]] = mapped_column(String(100))
    changed_by: Mapped[str] = mapped_column(String(100))
    change_summary: Mapped[Optional[str]] = mapped_column(String(1000))

    policy: Mapped["DecisionPolicy"] = relationship(back_populates="history")

class PolicyStatistics(DecisionBase):
    """
    Aggregated metrics for policy effectiveness.
    """
    __tablename__ = "security_decision_policy_statistics"

    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decision_policies.id"), index=True)
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    override_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_eval_time_ms: Mapped[float] = mapped_column(Float, default=0.0)

class DecisionPolicyReference(DecisionBase):
    """
    Link between a decision and the policy that influenced it.
    """
    __tablename__ = "security_decision_policy_refs"

    decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decisions.id"), index=True)
    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decision_policies.id"), index=True)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)

    decision: Mapped["Decision"] = relationship("Decision", back_populates="policy_ref")
