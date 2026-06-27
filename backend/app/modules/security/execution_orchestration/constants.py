"""
Constants for the Execution Orchestration Engine.

Mirrors the style of decision_engine/constants.py,
decision_strategy/constants.py, and decision_approval/constants.py.

This module defines:
  - The package lifecycle state machine (CREATED → ARCHIVED)
  - Validation/readiness enums
  - Pipeline stage identifiers
  - Rejection reasons (canonical strings for queryability)
  - Observability thresholds

NO execution logic lives here — only data shapes that the rest of
the module agrees on.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, Set


# ─────────────────────────────────────────────────────────────────────
#  Package State Machine
# ─────────────────────────────────────────────────────────────────────
class ExecutionPackageState(str, Enum):
    """
    Lifecycle states for an `ExecutionPackage`.

      NULL → CREATED → READINESS_VALIDATING → READINESS_PASSED →
                                                 ├─→ BUILDING → BUILT → READY
                                                 ├─→ REJECTED
                                                 └─→ FAILED
      Any non-terminal → ARCHIVED (terminal)
    """
    CREATED              = "CREATED"
    READINESS_VALIDATING = "READINESS_VALIDATING"
    READINESS_PASSED     = "READINESS_PASSED"
    READINESS_FAILED     = "READINESS_FAILED"
    BUILDING             = "BUILDING"
    BUILT                = "BUILT"
    READY                = "READY"
    REJECTED             = "REJECTED"
    FAILED               = "FAILED"
    ARCHIVED             = "ARCHIVED"


VALID_EXECUTION_TRANSITIONS: Dict = {
    None:                                [ExecutionPackageState.CREATED],
    ExecutionPackageState.CREATED:              [ExecutionPackageState.READINESS_VALIDATING, ExecutionPackageState.REJECTED, ExecutionPackageState.ARCHIVED],
    ExecutionPackageState.READINESS_VALIDATING: [ExecutionPackageState.READINESS_PASSED, ExecutionPackageState.READINESS_FAILED, ExecutionPackageState.REJECTED, ExecutionPackageState.ARCHIVED],
    ExecutionPackageState.READINESS_PASSED:     [ExecutionPackageState.BUILDING, ExecutionPackageState.REJECTED, ExecutionPackageState.ARCHIVED],
    ExecutionPackageState.READINESS_FAILED:     [ExecutionPackageState.REJECTED, ExecutionPackageState.ARCHIVED],
    ExecutionPackageState.BUILDING:             [ExecutionPackageState.BUILT, ExecutionPackageState.FAILED, ExecutionPackageState.ARCHIVED],
    ExecutionPackageState.BUILT:                [ExecutionPackageState.READY, ExecutionPackageState.FAILED, ExecutionPackageState.ARCHIVED],
    ExecutionPackageState.READY:                [ExecutionPackageState.ARCHIVED],
    ExecutionPackageState.REJECTED:             [ExecutionPackageState.ARCHIVED],
    ExecutionPackageState.FAILED:               [ExecutionPackageState.ARCHIVED],
    ExecutionPackageState.ARCHIVED:             [],
}


TERMINAL_EXECUTION_STATES: Set[ExecutionPackageState] = {
    ExecutionPackageState.ARCHIVED,
}


# ─────────────────────────────────────────────────────────────────────
#  Readiness Outcome
# ─────────────────────────────────────────────────────────────────────
class ReadinessOutcome(str, Enum):
    """Result of a single readiness check."""
    PASSED  = "PASSED"
    WARNING = "WARNING"
    FAILED  = "FAILED"


# ─────────────────────────────────────────────────────────────────────
#  Readiness Factor
# ─────────────────────────────────────────────────────────────────────
class ReadinessFactor(str, Enum):
    """
    Pluggable readiness checks.  Future factors register via
    `ExecutionReadinessEngine.register(...)` without engine changes.
    """
    DECISION_READY         = "DECISION_READY"
    APPROVAL_COMPLETE      = "APPROVAL_COMPLETE"
    STRATEGY_SELECTED      = "STRATEGY_SELECTED"
    REPOSITORY_AVAILABLE   = "REPOSITORY_AVAILABLE"
    ASSET_AVAILABLE        = "ASSET_AVAILABLE"
    DEPENDENCY_GRAPH_VALID = "DEPENDENCY_GRAPH_VALID"
    REQUIRED_METADATA      = "REQUIRED_METADATA"
    TENANT_ISOLATION       = "TENANT_ISOLATION"
    POLICY_COMPLIANCE      = "POLICY_COMPLIANCE"
    ENVIRONMENT_COMPAT     = "ENVIRONMENT_COMPATIBILITY"
    EXECUTION_WINDOW       = "EXECUTION_WINDOW"
    ROLLBACK_METADATA      = "ROLLBACK_METADATA"


# ─────────────────────────────────────────────────────────────────────
#  Rejection Reasons
# ─────────────────────────────────────────────────────────────────────
class ExecutionRejectionReason(str, Enum):
    """Canonical rejection reasons — stable, queryable strings."""
    MISSING_DECISION          = "MISSING_DECISION"
    MISSING_STRATEGY          = "MISSING_STRATEGY"
    MISSING_APPROVAL          = "MISSING_APPROVAL"
    APPROVAL_NOT_APPROVED     = "APPROVAL_NOT_APPROVED"
    DECISION_NOT_READY        = "DECISION_NOT_READY"
    REPOSITORY_UNAVAILABLE    = "REPOSITORY_UNAVAILABLE"
    ASSET_UNAVAILABLE         = "ASSET_UNAVAILABLE"
    INVALID_DEPENDENCY_GRAPH  = "INVALID_DEPENDENCY_GRAPH"
    MISSING_METADATA          = "MISSING_METADATA"
    TENANT_ISOLATION_BROKEN   = "TENANT_ISOLATION_BROKEN"
    POLICY_DENIED             = "POLICY_DENIED"
    ENVIRONMENT_INCOMPAT      = "ENVIRONMENT_INCOMPATIBLE"
    EXECUTION_WINDOW_INVALID  = "EXECUTION_WINDOW_INVALID"
    MISSING_ROLLBACK_METADATA = "MISSING_ROLLBACK_METADATA"
    DUPLICATE_PACKAGE         = "DUPLICATE_PACKAGE"
    INVALID_STRATEGY_STATE    = "INVALID_STRATEGY_STATE"


# ─────────────────────────────────────────────────────────────────────
#  Constraint Type — finer-grained than ReadinessFactor
# ─────────────────────────────────────────────────────────────────────
class ExecutionConstraintType(str, Enum):
    """
    Hard constraints that must be satisfied before BUILT → READY.

    Mirrors ReadinessFactor 1:1 but represents what BLOCKS execution,
    not what was CHECKED.
    """
    DECISION_READY        = "DECISION_READY"
    APPROVAL_APPROVED     = "APPROVAL_APPROVED"
    STRATEGY_APPROVED     = "STRATEGY_APPROVED"
    REPOSITORY_PRESENT    = "REPOSITORY_PRESENT"
    ASSET_PRESENT         = "ASSET_PRESENT"
    DEPENDENCY_RESOLVED   = "DEPENDENCY_RESOLVED"
    METADATA_COMPLETE     = "METADATA_COMPLETE"
    TENANT_MATCH          = "TENANT_MATCH"
    POLICY_PASSED         = "POLICY_PASSED"
    ENVIRONMENT_MATCH     = "ENVIRONMENT_MATCH"
    EXECUTION_WINDOW_OPEN = "EXECUTION_WINDOW_OPEN"
    ROLLBACK_PLANNED      = "ROLLBACK_PLANNED"


# ─────────────────────────────────────────────────────────────────────
#  Dependency Kind
# ─────────────────────────────────────────────────────────────────────
class ExecutionDependencyKind(str, Enum):
    """What kind of object is the dependency pointing at."""
    REPOSITORY  = "REPOSITORY"
    ASSET       = "ASSET"
    PACKAGE     = "PACKAGE"
    CVE         = "CVE"
    FINDING     = "FINDING"
    POLICY      = "POLICY"
    APPROVAL    = "APPROVAL"
    DECISION    = "DECISION"
    STRATEGY    = "STRATEGY"
    EXTERNAL    = "EXTERNAL"


# ─────────────────────────────────────────────────────────────────────
#  Pipeline Stages
# ─────────────────────────────────────────────────────────────────────
class ExecutionPipelineStage(str, Enum):
    """Pipeline stage identifiers — observability + audit."""
    DISCOVERY              = "DISCOVERY"
    READINESS_VALIDATION   = "READINESS_VALIDATION"
    DEPENDENCY_RESOLUTION  = "DEPENDENCY_RESOLUTION"
    CONSTRAINT_VALIDATION  = "CONSTRAINT_VALIDATION"
    PACKAGE_BUILD          = "PACKAGE_BUILD"
    PERSISTENCE            = "PERSISTENCE"
    AUDIT                  = "AUDIT"
    STATISTICS             = "STATISTICS"


# ─────────────────────────────────────────────────────────────────────
#  Audit Event Types
# ─────────────────────────────────────────────────────────────────────
class ExecutionAuditEvent(str, Enum):
    """Canonical event names written to the audit ledger."""
    PACKAGE_CREATED          = "PACKAGE_CREATED"
    READINESS_VALIDATED      = "READINESS_VALIDATED"
    READINESS_FAILED         = "READINESS_FAILED"
    DEPENDENCIES_RESOLVED    = "DEPENDENCIES_RESOLVED"
    CONSTRAINTS_VALIDATED    = "CONSTRAINTS_VALIDATED"
    PACKAGE_BUILT            = "PACKAGE_BUILT"
    PACKAGE_PERSISTED        = "PACKAGE_PERSISTED"
    PACKAGE_REJECTED         = "PACKAGE_REJECTED"
    PACKAGE_FAILED           = "PACKAGE_FAILED"
    PACKAGE_READY            = "PACKAGE_READY"
    PACKAGE_ARCHIVED         = "PACKAGE_ARCHIVED"


# ─────────────────────────────────────────────────────────────────────
#  Observability thresholds
# ─────────────────────────────────────────────────────────────────────
# TTL for the in-memory execution cache.
EXECUTION_CACHE_TTL_SECONDS = 300


__all__ = [
    "EXECUTION_CACHE_TTL_SECONDS",
    "ExecutionAuditEvent",
    "ExecutionConstraintType",
    "ExecutionDependencyKind",
    "ExecutionPackageState",
    "ExecutionPipelineStage",
    "ExecutionRejectionReason",
    "ReadinessFactor",
    "ReadinessOutcome",
    "TERMINAL_EXECUTION_STATES",
    "VALID_EXECUTION_TRANSITIONS",
]