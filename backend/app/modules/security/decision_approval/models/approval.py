"""
SQLAlchemy models for the Decision Approval Engine.

15 canonical models.  All inherit from `DecisionBase` (tenant_id,
correlation_id, version, trace_id, metadata_json) so the approval
module stays consistent with the decision_engine / decision_strategy
modules.

Indexes are defined per the spec:
    tenant_id, decision_id, approval_state, approval_type, approver_id,
    created_at — plus the obvious composite indexes.
"""
from __future__ import annotations
from typing import Optional, List
from sqlalchemy import (
    String, ForeignKey, JSON, Integer, Boolean,
    Enum as SAEnum, Float, DateTime, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.security.decision_engine.models.base import DecisionBase
from ..constants import (
    ApprovalOutcome,
    ApprovalRequirementMode,
    ApprovalState,
    ApprovalType,
)


# ─────────────────────────────────────────────────────────────────────
#  1. ApprovalRequest — root entity
# ─────────────────────────────────────────────────────────────────────
class ApprovalRequest(DecisionBase):
    """
    The aggregate root for an approval flow.

    One per (decision, strategy) — each request enumerates the
    requirement chain and accumulates per-actor decisions.
    """
    __tablename__ = "security_decision_approvals"
    __table_args__ = (
        Index("ix_apr_tenant",          "tenant_id"),
        Index("ix_apr_decision",        "decision_id"),
        Index("ix_apr_strategy",        "strategy_id"),
        Index("ix_apr_state",           "approval_state"),
        Index("ix_apr_type",            "approval_type"),
        Index("ix_apr_mode",            "requirement_mode"),
        Index("ix_apr_created_at",      "created_at"),
        Index("ix_apr_tenant_state",    "tenant_id", "approval_state"),
        Index("ix_apr_tenant_type",     "tenant_id", "approval_type"),
        Index("ix_apr_state_created",   "approval_state", "created_at"),
    )

    decision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decisions.id"), nullable=False, index=True
    )
    strategy_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("security_decision_strategies.id"),
        nullable=True, index=True,
    )

    approval_state: Mapped[ApprovalState] = mapped_column(
        SAEnum(ApprovalState, name="approval_state_enum"),
        default=ApprovalState.CREATED, nullable=False,
    )
    approval_type:  Mapped[ApprovalType] = mapped_column(
        SAEnum(ApprovalType, name="approval_type_enum"),
        default=ApprovalType.SECURITY, nullable=False,
    )
    requirement_mode: Mapped[ApprovalRequirementMode] = mapped_column(
        SAEnum(ApprovalRequirementMode, name="approval_requirement_mode_enum"),
        default=ApprovalRequirementMode.SINGLE, nullable=False,
    )

    summary:        Mapped[Optional[str]] = mapped_column(String(2000))
    business_justification:  Mapped[Optional[str]] = mapped_column(String(2000))
    technical_justification: Mapped[Optional[str]] = mapped_column(String(2000))

    risk_score:        Mapped[float] = mapped_column(Float, default=0.0)
    criticality_score: Mapped[float] = mapped_column(Float, default=0.0)
    composite_score:   Mapped[float] = mapped_column(Float, default=0.0)
    confidence:        Mapped[float] = mapped_column(Float, default=0.0)

    expires_at:     Mapped[Optional[str]]   = mapped_column(String(50), nullable=True)
    is_emergency:   Mapped[bool]           = mapped_column(Boolean, default=False)
    auto_decided:   Mapped[bool]           = mapped_column(Boolean, default=False)
    blocked:        Mapped[bool]           = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[Optional[str]]  = mapped_column(String(1000))

    # Relationships
    decisions:     Mapped[List["ApprovalDecision"]]      = relationship(back_populates="request", cascade="all, delete-orphan")
    requirements:  Mapped[List["ApprovalRequirement"]]   = relationship(back_populates="request", cascade="all, delete-orphan")
    actors:        Mapped[List["ApprovalActor"]]         = relationship(back_populates="request", cascade="all, delete-orphan")
    groups:        Mapped[List["ApprovalGroup"]]         = relationship(back_populates="request", cascade="all, delete-orphan")
    reasons:       Mapped[List["ApprovalReason"]]        = relationship(back_populates="request", cascade="all, delete-orphan")
    constraints:   Mapped[List["ApprovalConstraint"]]    = relationship(back_populates="request", cascade="all, delete-orphan")
    evidence:      Mapped[List["ApprovalEvidence"]]      = relationship(back_populates="request", cascade="all, delete-orphan")
    metadata_rows: Mapped[List["ApprovalMetadata"]]      = relationship(back_populates="request", cascade="all, delete-orphan")
    history:       Mapped[List["ApprovalHistory"]]       = relationship(back_populates="request", cascade="all, delete-orphan")
    versions:      Mapped[List["ApprovalVersion"]]       = relationship(back_populates="request", cascade="all, delete-orphan")
    audit:         Mapped[List["ApprovalAudit"]]         = relationship(back_populates="request", cascade="all, delete-orphan")
    statistics_rows: Mapped[List["ApprovalStatistics"]]   = relationship(back_populates="request", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────
#  2. ApprovalDecision — one row per actor decision
# ─────────────────────────────────────────────────────────────────────
class ApprovalDecision(DecisionBase):
    """A single actor's vote on an ApprovalRequest."""
    __tablename__ = "security_decision_approval_decisions"
    __table_args__ = (
        Index("ix_aprd_request",  "request_id"),
        Index("ix_aprd_approver", "approver_id"),
        Index("ix_aprd_outcome",  "outcome"),
        Index("ix_aprd_request_outcome", "request_id", "outcome"),
    )

    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=False, index=True
    )
    approver_id:  Mapped[str]           = mapped_column(String(100), nullable=False, index=True)
    approver_role: Mapped[Optional[str]] = mapped_column(String(100))
    outcome:      Mapped[ApprovalOutcome] = mapped_column(
        SAEnum(ApprovalOutcome, name="approval_outcome_enum"),
        default=ApprovalOutcome.PENDING, nullable=False,
    )
    rationale:    Mapped[Optional[str]]  = mapped_column(String(2000))
    decided_at:   Mapped[Optional[str]]  = mapped_column(String(50))

    request: Mapped["ApprovalRequest"] = relationship(back_populates="decisions")


# ─────────────────────────────────────────────────────────────────────
#  3. ApprovalPolicy — pluggable policy descriptor
# ─────────────────────────────────────────────────────────────────────
class ApprovalPolicy(DecisionBase):
    """
    A named, versioned policy descriptor.

    Policies register themselves via `ApprovalRegistry.register(...)`.
    The ApprovalPolicyEngine never references a specific policy by name.
    """
    __tablename__ = "security_decision_approval_policies"
    __table_args__ = (
        Index("ix_appol_tenant",   "tenant_id"),
        Index("ix_appol_name",     "policy_name"),
        Index("ix_appol_version",  "policy_version"),
        Index("ix_appol_active",   "is_active"),
    )

    policy_name:     Mapped[str]   = mapped_column(String(200), nullable=False)
    policy_version:  Mapped[int]   = mapped_column(Integer, nullable=False, default=1)
    description:     Mapped[Optional[str]] = mapped_column(String(2000))
    is_active:       Mapped[bool]  = mapped_column(Boolean, default=True)
    priority:        Mapped[int]   = mapped_column(Integer, default=100)

    # Snapshot of the policy's evaluation factors and thresholds.
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    rules: Mapped[List["ApprovalRule"]] = relationship(back_populates="policy", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────
#  4. ApprovalRule — one row per rule inside an ApprovalPolicy
# ─────────────────────────────────────────────────────────────────────
class ApprovalRule(DecisionBase):
    """A single rule (factor + threshold + action) inside a policy."""
    __tablename__ = "security_decision_approval_rules"
    __table_args__ = (
        Index("ix_aprule_policy", "policy_id"),
        Index("ix_aprule_factor", "factor"),
    )

    policy_id:   Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approval_policies.id"), nullable=False, index=True
    )
    factor:      Mapped[str] = mapped_column(String(100), nullable=False)
    operator:    Mapped[str] = mapped_column(String(20),  nullable=False)  # GT, GTE, LT, LTE, EQ, IN, BETWEEN
    threshold:   Mapped[float] = mapped_column(Float, default=0.0)
    weight:      Mapped[float] = mapped_column(Float, default=0.0)
    action:      Mapped[str] = mapped_column(String(50),  nullable=False)  # REQUIRE_APPROVAL, AUTO_APPROVE, AUTO_REJECT
    notes:       Mapped[Optional[str]] = mapped_column(String(2000))

    policy: Mapped["ApprovalPolicy"] = relationship(back_populates="rules")


# ─────────────────────────────────────────────────────────────────────
#  5. ApprovalRequirement — one row per required approver slot
# ─────────────────────────────────────────────────────────────────────
class ApprovalRequirement(DecisionBase):
    """One slot in the approval chain."""
    __tablename__ = "security_decision_approval_requirements"
    __table_args__ = (
        Index("ix_apreq_request",  "request_id"),
        Index("ix_apreq_role",     "required_role"),
        Index("ix_apreq_order",    "sequence_order"),
    )

    request_id:     Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=False, index=True
    )
    required_role:  Mapped[str] = mapped_column(String(100), nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, default=1)
    is_mandatory:   Mapped[bool] = mapped_column(Boolean, default=True)
    description:    Mapped[Optional[str]] = mapped_column(String(2000))

    request: Mapped["ApprovalRequest"] = relationship(back_populates="requirements")


# ─────────────────────────────────────────────────────────────────────
#  6. ApprovalEvidence — supporting data
# ─────────────────────────────────────────────────────────────────────
class ApprovalEvidence(DecisionBase):
    """A piece of evidence backing a reason or decision."""
    __tablename__ = "security_decision_approval_evidence"
    __table_args__ = (
        Index("ix_ape_request", "request_id"),
    )

    request_id:     Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=False, index=True
    )
    evidence_type:  Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_value: Mapped[str] = mapped_column(String(4000), nullable=False)
    source:         Mapped[Optional[str]] = mapped_column(String(200))

    request: Mapped["ApprovalRequest"] = relationship(back_populates="evidence")


# ─────────────────────────────────────────────────────────────────────
#  7. ApprovalReason — why a particular requirement applies
# ─────────────────────────────────────────────────────────────────────
class ApprovalReason(DecisionBase):
    """A reason why a particular approver or rule was triggered."""
    __tablename__ = "security_decision_approval_reasons"
    __table_args__ = (
        Index("ix_aprsn_request", "request_id"),
        Index("ix_aprsn_code",    "reason_code"),
    )

    request_id:  Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=False, index=True
    )
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    category:    Mapped[str] = mapped_column(String(50),  default="POLICY")

    request: Mapped["ApprovalRequest"] = relationship(back_populates="reasons")


# ─────────────────────────────────────────────────────────────────────
#  8. ApprovalConstraint — preconditions on the request
# ─────────────────────────────────────────────────────────────────────
class ApprovalConstraint(DecisionBase):
    """A hard precondition (e.g. all approvers resolved, policy exists)."""
    __tablename__ = "security_decision_approval_constraints"
    __table_args__ = (
        Index("ix_apc_request", "request_id"),
        Index("ix_apc_type",    "constraint_type"),
    )

    request_id:     Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=False, index=True
    )
    constraint_type: Mapped[str]  = mapped_column(String(100), nullable=False)
    is_met:          Mapped[bool] = mapped_column(Boolean, default=False)
    details:         Mapped[Optional[str]] = mapped_column(String(2000))

    request: Mapped["ApprovalRequest"] = relationship(back_populates="constraints")


# ─────────────────────────────────────────────────────────────────────
#  9. ApprovalMetadata — free-form key/value
# ─────────────────────────────────────────────────────────────────────
class ApprovalMetadata(DecisionBase):
    """Key/value metadata attached to an ApprovalRequest."""
    __tablename__ = "security_decision_approval_metadata"
    __table_args__ = (
        Index("ix_apmd_request", "request_id"),
        Index("ix_apmd_key",     "key"),
    )

    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=False, index=True
    )
    key:        Mapped[str] = mapped_column(String(128), nullable=False)
    value:      Mapped[str] = mapped_column(String(4000))

    request: Mapped["ApprovalRequest"] = relationship(back_populates="metadata_rows")


# ─────────────────────────────────────────────────────────────────────
#  10. ApprovalHistory — state-transition audit
# ─────────────────────────────────────────────────────────────────────
class ApprovalHistory(DecisionBase):
    """State-change audit for an ApprovalRequest."""
    __tablename__ = "security_decision_approval_history"
    __table_args__ = (
        Index("ix_aph_request",  "request_id"),
        Index("ix_aph_to_state", "to_state"),
        Index("ix_aph_at",       "changed_at"),
    )

    request_id:  Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=False, index=True
    )
    from_state:  Mapped[Optional[ApprovalState]] = mapped_column(
        SAEnum(ApprovalState, name="approval_history_from_enum"), nullable=True,
    )
    to_state:    Mapped[ApprovalState] = mapped_column(
        SAEnum(ApprovalState, name="approval_history_to_enum"), nullable=False,
    )
    changed_by:    Mapped[str] = mapped_column(String(100), nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(String(2000))
    changed_at:    Mapped[Optional[str]] = mapped_column(String(50))

    request: Mapped["ApprovalRequest"] = relationship(back_populates="history")


# ─────────────────────────────────────────────────────────────────────
#  11. ApprovalVersion — versioned snapshot
# ─────────────────────────────────────────────────────────────────────
class ApprovalVersion(DecisionBase):
    """Snapshot of an ApprovalRequest for rollback / audit."""
    __tablename__ = "security_decision_approval_versions"
    __table_args__ = (
        Index("ix_apv_request", "request_id"),
        Index("ix_apv_version", "version_number"),
    )

    request_id:    Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot:       Mapped[dict] = mapped_column(JSON, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(String(2000))

    request: Mapped["ApprovalRequest"] = relationship(back_populates="versions")


# ─────────────────────────────────────────────────────────────────────
#  12. ApprovalStatistics — aggregate metrics
# ─────────────────────────────────────────────────────────────────────
class ApprovalStatistics(DecisionBase):
    """Aggregate metrics per (tenant, approval_type, approval_state)."""
    __tablename__ = "security_decision_approval_statistics"
    __table_args__ = (
        Index("ix_aps_tenant",  "tenant_id"),
        Index("ix_aps_type",    "approval_type"),
        Index("ix_aps_state",   "approval_state"),
        Index("ix_aps_tenant_type", "tenant_id", "approval_type"),
    )

    approval_type:   Mapped[ApprovalType] = mapped_column(
        SAEnum(ApprovalType, name="approval_statistics_type_enum"), index=True,
    )
    approval_state:  Mapped[ApprovalState] = mapped_column(
        SAEnum(ApprovalState, name="approval_statistics_state_enum"), index=True,
    )
    count:           Mapped[int]   = mapped_column(Integer, default=0)
    avg_duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    avg_chain_length: Mapped[float] = mapped_column(Float, default=0.0)
    automatic_count: Mapped[int]   = mapped_column(Integer, default=0)
    manual_count:    Mapped[int]   = mapped_column(Integer, default=0)

    request_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=True,
    )
    request: Mapped[Optional["ApprovalRequest"]] = relationship(back_populates="statistics_rows")


# ─────────────────────────────────────────────────────────────────────
#  13. ApprovalAudit — append-only audit ledger
# ─────────────────────────────────────────────────────────────────────
class ApprovalAudit(DecisionBase):
    """
    Append-only audit ledger entry.

    One row per significant event (created, validated, decision submitted,
    auto-decided, expired, cancelled, archived).
    """
    __tablename__ = "security_decision_approval_audit"
    __table_args__ = (
        Index("ix_apa_request",  "request_id"),
        Index("ix_apa_event",    "event_type"),
        Index("ix_apa_actor",    "actor_id"),
        Index("ix_apa_at",       "occurred_at"),
    )

    request_id:  Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=False, index=True
    )
    event_type:  Mapped[str]           = mapped_column(String(100), nullable=False)
    actor_id:    Mapped[Optional[str]] = mapped_column(String(100))
    actor_role:  Mapped[Optional[str]] = mapped_column(String(100))
    details:     Mapped[Optional[dict]] = mapped_column(JSON)
    occurred_at: Mapped[Optional[str]] = mapped_column(String(50))

    request: Mapped["ApprovalRequest"] = relationship(back_populates="audit")


# ─────────────────────────────────────────────────────────────────────
#  14. ApprovalActor — concrete user/group fulfilling a slot
# ─────────────────────────────────────────────────────────────────────
class ApprovalActor(DecisionBase):
    """
    A specific user or system identity bound to an approval slot.

    One requirement → 1..N actors (delegation, multi-owner groups).
    """
    __tablename__ = "security_decision_approval_actors"
    __table_args__ = (
        Index("ix_apa_request", "request_id"),
        Index("ix_apa_actor",   "actor_id"),
        Index("ix_apa_role",    "role"),
    )

    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=False, index=True
    )
    actor_id:   Mapped[str]           = mapped_column(String(100), nullable=False)
    role:       Mapped[str]           = mapped_column(String(100), nullable=False)
    is_primary: Mapped[bool]           = mapped_column(Boolean, default=True)
    delegated_by: Mapped[Optional[str]] = mapped_column(String(100))

    request: Mapped["ApprovalRequest"] = relationship(back_populates="actors")


# ─────────────────────────────────────────────────────────────────────
#  15. ApprovalGroup — logical group of actors
# ─────────────────────────────────────────────────────────────────────
class ApprovalGroup(DecisionBase):
    """
    A logical group (e.g. 'security-leads', 'platform-oncall') that
    can collectively satisfy a requirement.
    """
    __tablename__ = "security_decision_approval_groups"
    __table_args__ = (
        Index("ix_apg_request", "request_id"),
        Index("ix_apg_name",    "group_name"),
    )

    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"), nullable=False, index=True
    )
    group_name: Mapped[str]           = mapped_column(String(200), nullable=False)
    member_ids: Mapped[Optional[str]] = mapped_column(String(4000))  # JSON-encoded list
    quorum:     Mapped[int]           = mapped_column(Integer, default=1)

    request: Mapped["ApprovalRequest"] = relationship(back_populates="groups")


__all__ = [
    "ApprovalRequest",
    "ApprovalDecision",
    "ApprovalPolicy",
    "ApprovalRule",
    "ApprovalRequirement",
    "ApprovalEvidence",
    "ApprovalReason",
    "ApprovalConstraint",
    "ApprovalMetadata",
    "ApprovalHistory",
    "ApprovalVersion",
    "ApprovalStatistics",
    "ApprovalAudit",
    "ApprovalActor",
    "ApprovalGroup",
]   # 15 models
