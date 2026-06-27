"""
SQLAlchemy models for the Execution Orchestration Engine.

12 canonical models.  All inherit from `DecisionBase` (tenant_id,
correlation_id, version, trace_id, metadata_json) so this module
stays consistent with the decision_engine / decision_strategy /
decision_approval modules.

Indexes are defined per the spec:
    tenant_id, decision_id, package_state, package_version, created_at
    — plus the obvious composite indexes.

NO execution semantics live in these models.  They are durable
artifacts only.
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
    ExecutionConstraintType,
    ExecutionDependencyKind,
    ExecutionPackageState,
    ReadinessFactor,
    ReadinessOutcome,
)


# ─────────────────────────────────────────────────────────────────────
#  1. ExecutionPackage — root entity
# ─────────────────────────────────────────────────────────────────────
class ExecutionPackage(DecisionBase):
    """
    The aggregate root for an immutable, deterministic execution
    package.  One Decision + Strategy + Approval chain maps to exactly
    one `ExecutionPackage` once all readiness + dependency + constraint
    checks have passed.

    The package is INTENTIONALLY content-light at this layer; the
    detail rows live on `ExecutionDependency` / `ExecutionConstraint` /
    `ExecutionRequirement` / `ExecutionMetadata`.
    """
    __tablename__ = "security_execution_packages"
    __table_args__ = (
        Index("ix_epkg_tenant",         "tenant_id"),
        Index("ix_epkg_decision",       "decision_id"),
        Index("ix_epkg_strategy",       "strategy_id"),
        Index("ix_epkg_approval",       "approval_id"),
        Index("ix_epkg_state",          "package_state"),
        Index("ix_epkg_version",        "package_version"),
        Index("ix_epkg_created_at",     "created_at"),
        Index("ix_epkg_tenant_state",   "tenant_id", "package_state"),
        Index("ix_epkg_state_created",  "package_state", "created_at"),
        Index("ix_epkg_decision_state", "decision_id", "package_state"),
    )

    decision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_decisions.id"), nullable=False, index=True,
    )
    strategy_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("security_decision_strategies.id"),
        nullable=True, index=True,
    )
    approval_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("security_decision_approvals.id"),
        nullable=True, index=True,
    )

    package_state: Mapped[ExecutionPackageState] = mapped_column(
        SAEnum(ExecutionPackageState, name="execution_package_state_enum"),
        default=ExecutionPackageState.CREATED, nullable=False,
    )
    package_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    is_immutable:  Mapped[bool]           = mapped_column(Boolean, default=False)
    is_ready:      Mapped[bool]           = mapped_column(Boolean, default=False)
    is_rejected:   Mapped[bool]           = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(1000))

    # Snapshot of the originating decision.version at build time.
    decision_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    strategy_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    approval_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    summary:        Mapped[Optional[str]] = mapped_column(String(2000))
    payload_hash:   Mapped[Optional[str]] = mapped_column(String(128))

    # Aggregate counters (denormalised for fast UI reads).
    dependency_count: Mapped[int]   = mapped_column(Integer, default=0)
    constraint_count: Mapped[int]   = mapped_column(Integer, default=0)
    metadata_count:   Mapped[int]   = mapped_column(Integer, default=0)
    package_size_kb:  Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    preparation: Mapped[Optional["ExecutionPreparation"]] = relationship(
        back_populates="package", uselist=False, cascade="all, delete-orphan",
    )
    readiness:   Mapped[Optional["ExecutionReadiness"]]   = relationship(
        back_populates="package", uselist=False, cascade="all, delete-orphan",
    )
    dependencies: Mapped[List["ExecutionDependency"]] = relationship(
        back_populates="package", cascade="all, delete-orphan",
    )
    constraints:  Mapped[List["ExecutionConstraint"]] = relationship(
        back_populates="package", cascade="all, delete-orphan",
    )
    requirements: Mapped[List["ExecutionRequirement"]] = relationship(
        back_populates="package", cascade="all, delete-orphan",
    )
    metadata_rows: Mapped[List["ExecutionMetadata"]] = relationship(
        back_populates="package", cascade="all, delete-orphan",
    )
    history:       Mapped[List["ExecutionHistory"]] = relationship(
        back_populates="package", cascade="all, delete-orphan",
    )
    versions:      Mapped[List["ExecutionVersion"]] = relationship(
        back_populates="package", cascade="all, delete-orphan",
    )
    statistics_rows: Mapped[List["ExecutionStatistics"]] = relationship(
        back_populates="package", cascade="all, delete-orphan",
    )
    audit:         Mapped[List["ExecutionAudit"]] = relationship(
        back_populates="package", cascade="all, delete-orphan",
    )
    summary_row:   Mapped[Optional["ExecutionSummary"]] = relationship(
        back_populates="package", uselist=False, cascade="all, delete-orphan",
    )


# ─────────────────────────────────────────────────────────────────────
#  2. ExecutionPreparation — pre-pipeline snapshot
# ─────────────────────────────────────────────────────────────────────
class ExecutionPreparation(DecisionBase):
    """Snapshot of the inputs gathered before the package is built."""
    __tablename__ = "security_execution_preparations"
    __table_args__ = (
        Index("ix_eprep_tenant",   "tenant_id"),
        Index("ix_eprep_decision", "decision_id"),
        Index("ix_eprep_package",  "package_id"),
    )

    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_execution_packages.id"),
        nullable=False, index=True, unique=True,
    )

    decision_snapshot:  Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    strategy_snapshot:  Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    approval_snapshot:  Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    context_snapshot:   Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    missing_fields: Mapped[Optional[str]] = mapped_column(String(4000))

    package: Mapped["ExecutionPackage"] = relationship(back_populates="preparation")


# ─────────────────────────────────────────────────────────────────────
#  3. ExecutionReadiness — overall readiness + per-factor verdicts
# ─────────────────────────────────────────────────────────────────────
class ExecutionReadiness(DecisionBase):
    """Readiness evaluation for the package."""
    __tablename__ = "security_execution_readiness"
    __table_args__ = (
        Index("ix_erd_tenant",   "tenant_id"),
        Index("ix_erd_package",  "package_id"),
        Index("ix_erd_outcome",  "outcome"),
    )

    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_execution_packages.id"),
        nullable=False, index=True, unique=True,
    )
    outcome: Mapped[ReadinessOutcome] = mapped_column(
        SAEnum(ReadinessOutcome, name="execution_readiness_outcome_enum"),
        default=ReadinessOutcome.PASSED, nullable=False,
    )

    factors_total:     Mapped[int]   = mapped_column(Integer, default=0)
    factors_passed:    Mapped[int]   = mapped_column(Integer, default=0)
    factors_warned:    Mapped[int]   = mapped_column(Integer, default=0)
    factors_failed:    Mapped[int]   = mapped_column(Integer, default=0)
    validation_ms:     Mapped[float] = mapped_column(Float, default=0.0)

    verdicts: Mapped[Optional[str]] = mapped_column(String(8000))  # JSON-encoded per-factor

    package: Mapped["ExecutionPackage"] = relationship(back_populates="readiness")


# ─────────────────────────────────────────────────────────────────────
#  4. ExecutionDependency — references resolved during READINESS
# ─────────────────────────────────────────────────────────────────────
class ExecutionDependency(DecisionBase):
    """
    A single dependency that must be present when the package is
    consumed by the future Remediation Engine (repository, asset,
    CVE, finding, …).
    """
    __tablename__ = "security_execution_dependencies"
    __table_args__ = (
        Index("ix_edep_tenant",   "tenant_id"),
        Index("ix_edep_package",  "package_id"),
        Index("ix_edep_kind",     "kind"),
        Index("ix_edep_resolved", "is_resolved"),
    )

    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_execution_packages.id"),
        nullable=False, index=True,
    )
    kind: Mapped[ExecutionDependencyKind] = mapped_column(
        SAEnum(ExecutionDependencyKind, name="execution_dependency_kind_enum"),
        nullable=False,
    )
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(500))

    is_resolved: Mapped[bool]           = mapped_column(Boolean, default=False)
    resolution_ms: Mapped[float]        = mapped_column(Float, default=0.0)
    notes:        Mapped[Optional[str]] = mapped_column(String(2000))

    package: Mapped["ExecutionPackage"] = relationship(back_populates="dependencies")


# ─────────────────────────────────────────────────────────────────────
#  5. ExecutionConstraint — preconditions that block execution
# ─────────────────────────────────────────────────────────────────────
class ExecutionConstraint(DecisionBase):
    """A hard precondition (must be satisfied before READY)."""
    __tablename__ = "security_execution_constraints"
    __table_args__ = (
        Index("ix_ec_tenant",  "tenant_id"),
        Index("ix_ec_package", "package_id"),
        Index("ix_ec_type",    "constraint_type"),
        Index("ix_ec_met",     "is_met"),
    )

    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_execution_packages.id"),
        nullable=False, index=True,
    )
    constraint_type: Mapped[ExecutionConstraintType] = mapped_column(
        SAEnum(ExecutionConstraintType, name="execution_constraint_type_enum"),
        nullable=False,
    )
    is_met:     Mapped[bool]          = mapped_column(Boolean, default=False)
    severity:   Mapped[str]           = mapped_column(String(20), default="HARD")
    details:    Mapped[Optional[str]] = mapped_column(String(2000))

    package: Mapped["ExecutionPackage"] = relationship(back_populates="constraints")


# ─────────────────────────────────────────────────────────────────────
#  6. ExecutionRequirement — soft requirements (downtime, window, …)
# ─────────────────────────────────────────────────────────────────────
class ExecutionRequirement(DecisionBase):
    """A non-fatal requirement surfaced for the consumer's awareness."""
    __tablename__ = "security_execution_requirements"
    __table_args__ = (
        Index("ix_erq_tenant",  "tenant_id"),
        Index("ix_erq_package", "package_id"),
    )

    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_execution_packages.id"),
        nullable=False, index=True,
    )
    requirement_type: Mapped[str] = mapped_column(String(100), nullable=False)
    value:            Mapped[Optional[str]] = mapped_column(String(2000))
    is_mandatory:     Mapped[bool]          = mapped_column(Boolean, default=False)
    description:      Mapped[Optional[str]] = mapped_column(String(2000))

    package: Mapped["ExecutionPackage"] = relationship(back_populates="requirements")


# ─────────────────────────────────────────────────────────────────────
#  7. ExecutionMetadata — free-form key/value
# ─────────────────────────────────────────────────────────────────────
class ExecutionMetadata(DecisionBase):
    """Free-form key/value metadata attached to an ExecutionPackage."""
    __tablename__ = "security_execution_metadata"
    __table_args__ = (
        Index("ix_emd_tenant",  "tenant_id"),
        Index("ix_emd_package", "package_id"),
        Index("ix_emd_key",     "key"),
    )

    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_execution_packages.id"),
        nullable=False, index=True,
    )
    key:   Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(String(4000))

    package: Mapped["ExecutionPackage"] = relationship(back_populates="metadata_rows")


# ─────────────────────────────────────────────────────────────────────
#  8. ExecutionHistory — state-change audit
# ─────────────────────────────────────────────────────────────────────
class ExecutionHistory(DecisionBase):
    """State-change audit for an ExecutionPackage."""
    __tablename__ = "security_execution_history"
    __table_args__ = (
        Index("ix_eh_tenant",     "tenant_id"),
        Index("ix_eh_package",    "package_id"),
        Index("ix_eh_to_state",   "to_state"),
        Index("ix_eh_changed_at", "changed_at"),
    )

    package_id:  Mapped[str] = mapped_column(
        String(36), ForeignKey("security_execution_packages.id"),
        nullable=False, index=True,
    )
    from_state:  Mapped[Optional[ExecutionPackageState]] = mapped_column(
        SAEnum(ExecutionPackageState, name="execution_history_from_enum"), nullable=True,
    )
    to_state:    Mapped[ExecutionPackageState] = mapped_column(
        SAEnum(ExecutionPackageState, name="execution_history_to_enum"), nullable=False,
    )
    changed_by:    Mapped[str] = mapped_column(String(100), nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(String(2000))
    changed_at:    Mapped[Optional[str]] = mapped_column(String(50))

    package: Mapped["ExecutionPackage"] = relationship(back_populates="history")


# ─────────────────────────────────────────────────────────────────────
#  9. ExecutionVersion — versioned snapshot
# ─────────────────────────────────────────────────────────────────────
class ExecutionVersion(DecisionBase):
    """Snapshot of an ExecutionPackage for rollback / audit."""
    __tablename__ = "security_execution_versions"
    __table_args__ = (
        Index("ix_ev_tenant",   "tenant_id"),
        Index("ix_ev_package",  "package_id"),
        Index("ix_ev_version",  "version_number"),
    )

    package_id:     Mapped[str] = mapped_column(
        String(36), ForeignKey("security_execution_packages.id"),
        nullable=False, index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot:       Mapped[dict] = mapped_column(JSON, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(String(2000))

    package: Mapped["ExecutionPackage"] = relationship(back_populates="versions")


# ─────────────────────────────────────────────────────────────────────
#  10. ExecutionStatistics — aggregate metrics
# ─────────────────────────────────────────────────────────────────────
class ExecutionStatistics(DecisionBase):
    """Aggregate metrics per (tenant, package_state)."""
    __tablename__ = "security_execution_statistics"
    __table_args__ = (
        Index("ix_es_tenant",  "tenant_id"),
        Index("ix_es_state",   "package_state"),
        Index("ix_es_tenant_state", "tenant_id", "package_state"),
    )

    package_state: Mapped[ExecutionPackageState] = mapped_column(
        SAEnum(ExecutionPackageState, name="execution_statistics_state_enum"),
        index=True, nullable=False,
    )
    count:               Mapped[int]   = mapped_column(Integer, default=0)
    avg_duration_ms:     Mapped[float] = mapped_column(Float, default=0.0)
    avg_package_size_kb: Mapped[float] = mapped_column(Float, default=0.0)
    rejected_count:      Mapped[int]   = mapped_column(Integer, default=0)
    ready_count:         Mapped[int]   = mapped_column(Integer, default=0)

    package_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("security_execution_packages.id"),
        nullable=True,
    )
    package: Mapped[Optional["ExecutionPackage"]] = relationship(back_populates="statistics_rows")


# ─────────────────────────────────────────────────────────────────────
#  11. ExecutionAudit — append-only ledger
# ─────────────────────────────────────────────────────────────────────
class ExecutionAudit(DecisionBase):
    """Append-only audit ledger — one row per significant event."""
    __tablename__ = "security_execution_audit"
    __table_args__ = (
        Index("ix_ea_tenant",   "tenant_id"),
        Index("ix_ea_package",  "package_id"),
        Index("ix_ea_event",    "event_type"),
        Index("ix_ea_actor",    "actor_id"),
        Index("ix_ea_at",       "occurred_at"),
    )

    package_id:  Mapped[str] = mapped_column(
        String(36), ForeignKey("security_execution_packages.id"),
        nullable=False, index=True,
    )
    event_type:  Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id:    Mapped[Optional[str]] = mapped_column(String(100))
    actor_role:  Mapped[Optional[str]] = mapped_column(String(100))
    details:     Mapped[Optional[dict]] = mapped_column(JSON)
    occurred_at: Mapped[Optional[str]] = mapped_column(String(50))

    package: Mapped["ExecutionPackage"] = relationship(back_populates="audit")


# ─────────────────────────────────────────────────────────────────────
#  12. ExecutionSummary — denormalised "ready-to-show" view
# ─────────────────────────────────────────────────────────────────────
class ExecutionSummary(DecisionBase):
    """
    Denormalised summary of the package for fast read-only rendering.
    Populated by the pipeline at BUILT time; queried by the API.
    """
    __tablename__ = "security_execution_summary"
    __table_args__ = (
        Index("ix_esu_tenant",   "tenant_id"),
        Index("ix_esu_package",  "package_id"),
        Index("ix_esu_state",    "package_state"),
    )

    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("security_execution_packages.id"),
        nullable=False, index=True, unique=True,
    )

    readiness_status:    Mapped[str] = mapped_column(String(50),  default="UNKNOWN")
    validation_results:  Mapped[dict] = mapped_column(JSON, default=dict)
    selected_strategy:   Mapped[Optional[str]] = mapped_column(String(200))
    approval_status:     Mapped[str] = mapped_column(String(50),  default="UNKNOWN")
    dependency_count:    Mapped[int]   = mapped_column(Integer, default=0)
    constraint_passed:   Mapped[int]   = mapped_column(Integer, default=0)
    constraint_failed:   Mapped[int]   = mapped_column(Integer, default=0)
    package_metadata:    Mapped[dict] = mapped_column(JSON, default=dict)
    package_timeline:    Mapped[list] = mapped_column(JSON, default=list)

    package: Mapped["ExecutionPackage"] = relationship(back_populates="summary_row")


__all__ = [
    "ExecutionPackage",
    "ExecutionPreparation",
    "ExecutionReadiness",
    "ExecutionDependency",
    "ExecutionConstraint",
    "ExecutionRequirement",
    "ExecutionMetadata",
    "ExecutionHistory",
    "ExecutionVersion",
    "ExecutionStatistics",
    "ExecutionAudit",
    "ExecutionSummary",
]   # 12 models