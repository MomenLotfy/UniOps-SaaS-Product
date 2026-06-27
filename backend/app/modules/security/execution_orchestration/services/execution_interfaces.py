"""
Interfaces and shared dataclasses for the Execution Orchestration Engine.

Mirrors `decision_strategy/services/strategy_interfaces.py` and
`decision_approval/services/approval_interfaces.py`.

This module defines:
  - The in-memory data containers (`ExecutionCandidateData`,
    `ExecutionEvaluationResult`, `ExecutionDependencySpec`,
    `ExecutionConstraintSpec`, `ExecutionRequirementSpec`,
    `ReadinessVerdict`, `ReadinessFactorResult`)
  - Abstract contracts (`IExecutionReadinessCheck`,
    `IExecutionValidator`, `IExecutionRepository`,
    `IExecutionLifecycleManager`, `IExecutionDependencyResolver`,
    `IExecutionConstraintValidator`,
    `IExecutionPreparationService`, `IExecutionCache`)

NO execution semantics live here — only data shapes that the rest of
the module agrees on.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..constants import (
    ExecutionConstraintType,
    ExecutionDependencyKind,
    ExecutionPackageState,
    ReadinessFactor,
    ReadinessOutcome,
)


# ─────────────────────────────────────────────────────────────────────
#  Readiness — per-factor verdict
# ─────────────────────────────────────────────────────────────────────
@dataclass
class ReadinessFactorResult:
    """Verdict for one `ReadinessFactor`."""
    factor: ReadinessFactor
    outcome: ReadinessOutcome
    rationale: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0

    @property
    def is_passed(self) -> bool:
        return self.outcome == ReadinessOutcome.PASSED

    @property
    def is_warned(self) -> bool:
        return self.outcome == ReadinessOutcome.WARNING

    @property
    def is_failed(self) -> bool:
        return self.outcome == ReadinessOutcome.FAILED


# ─────────────────────────────────────────────────────────────────────
#  Dependency — soft reference that must be present
# ─────────────────────────────────────────────────────────────────────
@dataclass
class ExecutionDependencySpec:
    """An in-memory spec for one resolved-or-not dependency."""
    kind: ExecutionDependencyKind
    reference: str
    display_name: Optional[str] = None
    is_resolved: bool = False
    notes: Optional[str] = None
    resolution_ms: float = 0.0


# ─────────────────────────────────────────────────────────────────────
#  Constraint — hard precondition that blocks execution
# ─────────────────────────────────────────────────────────────────────
@dataclass
class ExecutionConstraintSpec:
    """An in-memory spec for one constraint."""
    constraint_type: ExecutionConstraintType
    is_met: bool = False
    severity: str = "HARD"
    details: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────
#  Requirement — soft requirement surfaced to the consumer
# ─────────────────────────────────────────────────────────────────────
@dataclass
class ExecutionRequirementSpec:
    """An in-memory spec for one non-fatal requirement."""
    requirement_type: str
    value: Optional[str] = None
    is_mandatory: bool = False
    description: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────
#  Candidate — aggregated in-memory view of one ExecutionPackage
# ─────────────────────────────────────────────────────────────────────
@dataclass
class ExecutionCandidateData:
    """In-memory representation of one ExecutionPackage candidate.

    NOT an ORM row — that is `models.ExecutionPackage`.  This is the
    pipeline-friendly container used between Preparation → Readiness →
    Build.
    """
    tenant_id: str = "default"
    decision_id: str = ""
    strategy_id: Optional[str] = None
    approval_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None

    decision_version: Optional[int] = None
    strategy_version: Optional[int] = None
    approval_version: Optional[int] = None

    is_valid: bool = True
    rejection_reason: Optional[str] = None
    rejection_details: Optional[str] = None

    # Filled by ExecutionReadinessEngine
    readiness_factors: List[ReadinessFactorResult] = field(default_factory=list)
    readiness_total: int = 0
    readiness_passed: int = 0
    readiness_warned: int = 0
    readiness_failed: int = 0
    readiness_ms: float = 0.0

    # Filled by ExecutionDependencyResolver
    dependencies: List[ExecutionDependencySpec] = field(default_factory=list)

    # Filled by ExecutionConstraintValidator
    constraints: List[ExecutionConstraintSpec] = field(default_factory=list)

    # Filled by ExecutionPreparationService (user-input)
    requirements: List[ExecutionRequirementSpec] = field(default_factory=list)
    metadata: List[Tuple[str, str]] = field(default_factory=list)
    summary: Optional[str] = None

    # Pipeline bookkeeping
    package_size_kb: float = 0.0
    payload_hash: Optional[str] = None
    evaluation_duration_ms: int = 0


# ─────────────────────────────────────────────────────────────────────
#  Result — output of one full ExecutionEvaluationPipeline.run(...)
# ─────────────────────────────────────────────────────────────────────
@dataclass
class ExecutionEvaluationResult:
    """Final result of one execution-orchestration run."""
    tenant_id: str
    decision_id: str
    candidate: Optional[ExecutionCandidateData] = None
    package_id: Optional[str] = None
    final_state: ExecutionPackageState = ExecutionPackageState.CREATED
    ranking_stable: bool = True
    evaluation_duration_ms: int = 0
    rejection_reason: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────
#  Preparation snapshot — captured before the pipeline starts
# ─────────────────────────────────────────────────────────────────────
@dataclass
class ExecutionPreparationSnapshot:
    """Aggregated snapshot of the upstream inputs.

    Captured before the pipeline starts so the orchestrator can
    produce a fully-populated `ExecutionPreparation` row at the
    end without re-reading decision/strategy/approval tables.
    """
    tenant_id: str
    decision_id: str
    strategy_id: Optional[str] = None
    approval_id: Optional[str] = None
    decision_snapshot: Dict[str, Any] = field(default_factory=dict)
    strategy_snapshot: Dict[str, Any] = field(default_factory=dict)
    approval_snapshot: Dict[str, Any] = field(default_factory=dict)
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    is_complete: bool = False


# ─────────────────────────────────────────────────────────────────────
#  Abstract interfaces
# ─────────────────────────────────────────────────────────────────────
class IExecutionReadinessCheck(ABC):
    """Pluggable readiness check for one `ReadinessFactor`."""
    factor: ReadinessFactor = ReadinessFactor.DECISION_READY

    @abstractmethod
    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        """Return True if this check should run for the given candidate."""

    @abstractmethod
    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        """Return the per-factor verdict."""


class IExecutionReadinessEngine(ABC):
    """Coordinates the per-factor checks."""
    @abstractmethod
    def register(self, factor: ReadinessFactor, check: IExecutionReadinessCheck) -> None: ...

    @abstractmethod
    def run(self, candidate: ExecutionCandidateData, context: Any) -> List[ReadinessFactorResult]: ...


class IExecutionValidator(ABC):
    """Returns a list of error codes; [] means valid."""
    @abstractmethod
    def validate(self, candidate: ExecutionCandidateData) -> List[str]: ...


class IExecutionRepository(ABC):
    """Persistence boundary — production impl is SQLAlchemy."""
    @abstractmethod
    async def save_package(self, package: Any) -> Any: ...

    @abstractmethod
    async def get_package(self, package_id: str) -> Optional[Any]: ...

    @abstractmethod
    async def list_packages(
        self, tenant_id: str, *,
        state: Optional[ExecutionPackageState] = None,
        decision_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Any]: ...

    @abstractmethod
    async def list_history(self, package_id: str) -> List[Any]: ...

    @abstractmethod
    async def list_audit(self, package_id: str) -> List[Any]: ...

    @abstractmethod
    async def get_statistics(self, tenant_id: str) -> Dict[str, Any]: ...


class IExecutionLifecycleManager(ABC):
    """Transitions ExecutionPackageState with validity checks."""
    @abstractmethod
    def can_transition(self, from_state: ExecutionPackageState, to_state: ExecutionPackageState) -> bool: ...

    @abstractmethod
    async def transition(
        self, package_id: str, to_state: ExecutionPackageState, *,
        changed_by: str, reason: Optional[str] = None,
    ) -> Any: ...


class IExecutionDependencyResolver(ABC):
    """Resolves & validates every dependency required for execution."""
    @abstractmethod
    async def resolve(self, candidate: ExecutionCandidateData, context: Any) -> List[ExecutionDependencySpec]: ...


class IExecutionConstraintValidator(ABC):
    """Validates the 12 hard ExecutionConstraintType values."""
    @abstractmethod
    def validate(self, candidate: ExecutionCandidateData, context: Any) -> List[ExecutionConstraintSpec]: ...


class IExecutionPreparationService(ABC):
    """Snapshots Decision/Strategy/Approval/Context before the pipeline."""
    @abstractmethod
    def prepare(
        self, decision: Any, strategy: Any = None, approval: Any = None,
        *, tenant_id: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPreparationSnapshot: ...


class IExecutionCache(ABC):
    """In-memory TTL cache.  Not safe for multi-process deployments."""
    @abstractmethod
    def get(self, tenant_id: str, decision_id: str, context: Any) -> Optional[ExecutionEvaluationResult]: ...

    @abstractmethod
    def put(self, tenant_id: str, decision_id: str, context: Any,
            value: ExecutionEvaluationResult) -> None: ...

    @abstractmethod
    def invalidate(self, tenant_id: Optional[str] = None) -> None: ...


__all__ = [
    "ExecutionCandidateData",
    "ExecutionConstraintSpec",
    "ExecutionDependencySpec",
    "ExecutionEvaluationResult",
    "ExecutionPreparationSnapshot",
    "ExecutionRequirementSpec",
    "IExecutionCache",
    "IExecutionConstraintValidator",
    "IExecutionDependencyResolver",
    "IExecutionLifecycleManager",
    "IExecutionPreparationService",
    "IExecutionReadinessCheck",
    "IExecutionReadinessEngine",
    "IExecutionRepository",
    "IExecutionValidator",
    "ReadinessFactorResult",
]