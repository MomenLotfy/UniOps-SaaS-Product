from __future__ import annotations
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List
from sqlalchemy import (
    String, ForeignKey, JSON, DateTime, Integer, Boolean,
    Enum as SAEnum, Float, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.security.decision_engine.models.base import DecisionBase
from ..constants import StrategyType, StrategyState


class DecisionStrategy(DecisionBase):
    """
    Root entity for a chosen remediation strategy.

    One Decision → one DecisionStrategy (the winner).
    All considered alternatives live on `StrategyCandidate` rows.
    """
    __tablename__ = "security_decision_strategies"
    __table_args__ = (
        Index("ix_dstrat_tenant",     "tenant_id"),
        Index("ix_dstrat_decision",   "decision_id"),
        Index("ix_dstrat_strategy",   "strategy_type"),
        Index("ix_dstrat_state",      "state"),
        Index("ix_dstrat_priority",   "priority"),
        Index("ix_dstrat_tenant_state", "tenant_id", "state"),
    )

    decision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decisions.id"), index=True
    )
    plan_id:     Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("security_decision_plans.id"), nullable=True, index=True
    )

    strategy_type: Mapped[StrategyType] = mapped_column(
        SAEnum(StrategyType, name="strategy_type_enum"),
        default=StrategyType.NO_ACTION,
    )
    state: Mapped[StrategyState] = mapped_column(
        SAEnum(StrategyState, name="strategy_state_enum"),
        default=StrategyState.SELECTED,
    )

    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    confidence:        Mapped[float] = mapped_column(Float, default=0.0)
    risk_score:        Mapped[float] = mapped_column(Float, default=0.0)
    feasibility_score: Mapped[float] = mapped_column(Float, default=0.0)
    composite_score:   Mapped[float] = mapped_column(Float, default=0.0)

    business_justification: Mapped[Optional[str]] = mapped_column(String(2000))
    technical_justification: Mapped[Optional[str]] = mapped_column(String(2000))
    selection_reason:       Mapped[Optional[str]] = mapped_column(String(2000))
    rejected_reason:        Mapped[Optional[str]] = mapped_column(String(2000))

    expected_downtime_min: Mapped[Optional[int]] = mapped_column(Integer)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reversible:           Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    # Sprint 2 R17: ``lazy="selectin"`` ensures child collections are
    # auto-loaded after the parent, eliminating MissingGreenlet errors
    # when the parent is returned across session boundaries.
    candidates:  Mapped[List["StrategyCandidate"]]   = relationship(back_populates="strategy", lazy="selectin")
    constraints: Mapped[List["StrategyConstraint"]]  = relationship(back_populates="strategy", lazy="selectin")
    requirements: Mapped[List["StrategyRequirement"]] = relationship(back_populates="strategy", lazy="selectin")
    reasons:     Mapped[List["StrategyReason"]]      = relationship(back_populates="strategy", lazy="selectin")
    history:     Mapped[List["StrategyHistory"]]     = relationship(back_populates="strategy", lazy="selectin")
    versions:    Mapped[List["StrategyVersion"]]     = relationship(back_populates="strategy", lazy="selectin")


class StrategyCandidate(DecisionBase):
    """
    A single candidate considered during strategy evaluation.

    One DecisionStrategy → N StrategyCandidate rows (one per considered type).
    """
    __tablename__ = "security_decision_strategy_candidates"
    __table_args__ = (
        Index("ix_dsc_tenant",   "tenant_id"),
        Index("ix_dsc_strategy", "strategy_id"),
        Index("ix_dsc_type",     "candidate_type"),
    )

    strategy_id:   Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_strategies.id"), index=True
    )
    candidate_type: Mapped[StrategyType] = mapped_column(
        SAEnum(StrategyType, name="strategy_candidate_type_enum")
    )

    feasibility_score: Mapped[float] = mapped_column(Float, default=0.0)
    composite_score:   Mapped[float] = mapped_column(Float, default=0.0)
    risk_score:        Mapped[float] = mapped_column(Float, default=0.0)
    confidence:        Mapped[float] = mapped_column(Float, default=0.0)
    rank:              Mapped[Optional[int]] = mapped_column(Integer)

    is_valid:        Mapped[bool] = mapped_column(Boolean, default=True)
    rejected_reason: Mapped[Optional[str]] = mapped_column(String(255))

    strategy: Mapped["DecisionStrategy"] = relationship(back_populates="candidates")
    scores:   Mapped[List["StrategyScore"]]  = relationship(back_populates="candidate", lazy="selectin")
    ranking:  Mapped[Optional["StrategyRanking"]] = relationship(back_populates="candidate")


class StrategyScore(DecisionBase):
    """
    One row per scoring dimension for a candidate.

    Dimension names must match keys in `constants.SCORING_WEIGHTS`.
    """
    __tablename__ = "security_decision_strategy_scores"
    __table_args__ = (
        Index("ix_dsscr_candidate", "candidate_id"),
        Index("ix_dsscr_dimension", "dimension"),
    )

    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_strategy_candidates.id"), index=True
    )
    dimension:    Mapped[str] = mapped_column(String(100), nullable=False)
    value:        Mapped[float] = mapped_column(Float, default=0.0)
    weight:       Mapped[float] = mapped_column(Float, default=0.0)
    contribution: Mapped[float] = mapped_column(Float, default=0.0)  # value * weight
    rationale:    Mapped[Optional[str]] = mapped_column(String(1000))

    candidate: Mapped["StrategyCandidate"] = relationship(back_populates="scores")


class StrategyRanking(DecisionBase):
    """
    Stores the final ranking order for a candidate within an evaluation.
    """
    __tablename__ = "security_decision_strategy_rankings"
    __table_args__ = (
        Index("ix_dsr_candidate", "candidate_id"),
        Index("ix_dsr_rank",      "rank"),
    )

    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_strategy_candidates.id"), index=True
    )
    rank:         Mapped[int] = mapped_column(Integer, nullable=False)
    composite_score:    Mapped[float] = mapped_column(Float, default=0.0)
    feasibility_score:  Mapped[float] = mapped_column(Float, default=0.0)
    is_valid:           Mapped[bool]  = mapped_column(Boolean, default=True)
    rejection_reason:   Mapped[Optional[str]] = mapped_column(String(1000))

    candidate: Mapped["StrategyCandidate"] = relationship(back_populates="ranking")


class StrategyEvaluation(DecisionBase):
    """
    Audit of one full evaluation run for a Decision.

    One Decision → many StrategyEvaluation rows (one per pipeline run).
    """
    __tablename__ = "security_decision_strategy_evaluations"
    __table_args__ = (
        Index("ix_dse_tenant",   "tenant_id"),
        Index("ix_dse_decision", "decision_id"),
    )

    decision_id:    Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decisions.id"), index=True
    )
    selected_strategy_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("security_decision_strategies.id"), nullable=True
    )
    candidate_count:  Mapped[int]   = mapped_column(Integer, default=0)
    rejected_count:   Mapped[int]   = mapped_column(Integer, default=0)
    duration_ms:      Mapped[float] = mapped_column(Float, default=0.0)
    ranking_duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    selection_duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    notes:            Mapped[Optional[str]] = mapped_column(String(2000))


class StrategyConstraint(DecisionBase):
    """
    Hard preconditions that must be satisfied for a strategy to be viable.

    e.g. PATCH_EXISTING_VERSION requires `fixed_version` to be present.
    """
    __tablename__ = "security_decision_strategy_constraints"
    __table_args__ = (
        Index("ix_dscstrat_strategy", "strategy_id"),
        Index("ix_dscstrat_type",     "constraint_type"),
    )

    strategy_id:     Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_strategies.id"), index=True
    )
    constraint_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_met:          Mapped[bool] = mapped_column(Boolean, default=False)
    details:         Mapped[Optional[str]] = mapped_column(String(1000))

    strategy: Mapped["DecisionStrategy"] = relationship(back_populates="constraints")


class StrategyRequirement(DecisionBase):
    """
    Runtime requirements (downtime window, approver, etc.).
    """
    __tablename__ = "security_decision_strategy_requirements"
    __table_args__ = (
        Index("ix_dsreq_strategy", "strategy_id"),
        Index("ix_dsreq_type",     "requirement_type"),
    )

    strategy_id:      Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_strategies.id"), index=True
    )
    requirement_type: Mapped[str] = mapped_column(String(100), nullable=False)
    value:            Mapped[Optional[str]] = mapped_column(String(2000))

    strategy: Mapped["DecisionStrategy"] = relationship(back_populates="requirements")


class StrategyReason(DecisionBase):
    """
    Justification for a chosen strategy.

    Multiple reasons may apply (business, technical, compliance).
    """
    __tablename__ = "security_decision_strategy_reasons"
    __table_args__ = (
        Index("ix_dsr_strat", "strategy_id"),
        Index("ix_dsr_code",  "reason_code"),
    )

    strategy_id:  Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_strategies.id"), index=True
    )
    reason_code:  Mapped[str] = mapped_column(String(100), nullable=False)
    description:  Mapped[str] = mapped_column(String(2000), nullable=False)
    category:     Mapped[str] = mapped_column(String(50), default="TECHNICAL")  # BUSINESS|TECHNICAL|COMPLIANCE

    strategy: Mapped["DecisionStrategy"] = relationship(back_populates="reasons")
    evidence: Mapped[List["StrategyEvidence"]] = relationship(back_populates="reason", lazy="selectin")


class StrategyEvidence(DecisionBase):
    """
    Supporting data for a StrategyReason.
    """
    __tablename__ = "security_decision_strategy_evidence"
    __table_args__ = (
        Index("ix_dsev_reason", "reason_id"),
    )

    reason_id:      Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_strategy_reasons.id"), index=True
    )
    evidence_type:  Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_value: Mapped[str] = mapped_column(String(2000), nullable=False)

    reason: Mapped["StrategyReason"] = relationship(back_populates="evidence")


class StrategyMetadata(DecisionBase):
    """Key/value metadata attached to a DecisionStrategy."""
    __tablename__ = "security_decision_strategy_metadata"
    __table_args__ = (
        Index("ix_dsmeta_strategy", "strategy_id"),
    )

    strategy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_strategies.id"), index=True
    )
    key:         Mapped[str] = mapped_column(String(100), nullable=False)
    value:       Mapped[str] = mapped_column(String(2000))


class StrategyHistory(DecisionBase):
    """State-change audit for a DecisionStrategy."""
    __tablename__ = "security_decision_strategy_history"
    __table_args__ = (
        Index("ix_dsh_strategy",  "strategy_id"),
        Index("ix_dsh_to_state",  "to_state"),
    )

    strategy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_strategies.id"), index=True
    )
    from_state:  Mapped[Optional[StrategyState]] = mapped_column(
        SAEnum(StrategyState, name="strategy_state_enum"), nullable=True
    )
    to_state:    Mapped[StrategyState] = mapped_column(
        SAEnum(StrategyState, name="strategy_state_enum"), nullable=False
    )
    changed_by:    Mapped[str] = mapped_column(String(100), nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(String(1000))

    strategy: Mapped["DecisionStrategy"] = relationship(back_populates="history")


class StrategyStatistics(DecisionBase):
    """Aggregate metrics per (tenant, strategy_type, state)."""
    __tablename__ = "security_decision_strategy_statistics"
    __table_args__ = (
        Index("ix_dss_tenant",   "tenant_id"),
        Index("ix_dss_type",     "strategy_type"),
        Index("ix_dss_state",    "state"),
        Index("ix_dss_tenant_type", "tenant_id", "strategy_type"),
    )

    strategy_type:  Mapped[StrategyType] = mapped_column(
        SAEnum(StrategyType, name="strategy_statistics_type_enum"), index=True
    )
    state:          Mapped[StrategyState] = mapped_column(
        SAEnum(StrategyState, name="strategy_statistics_state_enum"), index=True
    )
    count:          Mapped[int]   = mapped_column(Integer, default=0)
    rejection_count: Mapped[int]  = mapped_column(Integer, default=0, nullable=False)
    avg_duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    avg_risk:       Mapped[float] = mapped_column(Float, default=0.0)


class StrategyVersion(DecisionBase):
    """Versioned snapshot of a DecisionStrategy for rollback / audit."""
    __tablename__ = "security_decision_strategy_versions"
    __table_args__ = (
        Index("ix_dsv_strategy", "strategy_id"),
        Index("ix_dsv_version",  "version_number"),
    )

    strategy_id:     Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decision_strategies.id"), index=True
    )
    version_number:  Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot:        Mapped[dict] = mapped_column(JSON, nullable=False)
    change_summary:  Mapped[Optional[str]] = mapped_column(String(1000))

    strategy: Mapped["DecisionStrategy"] = relationship(back_populates="versions")


# Re-export the decision_engine DecisionBase for callers that import
# everything from a single module.
__all__ = [
    "DecisionStrategy",
    "StrategyCandidate",
    "StrategyScore",
    "StrategyRanking",
    "StrategyEvaluation",
    "StrategyConstraint",
    "StrategyRequirement",
    "StrategyReason",
    "StrategyEvidence",
    "StrategyMetadata",
    "StrategyHistory",
    "StrategyStatistics",
    "StrategyVersion",
]
