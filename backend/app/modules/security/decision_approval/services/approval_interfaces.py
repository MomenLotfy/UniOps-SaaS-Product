"""
Interfaces and shared dataclasses for the Approval Engine.

Mirrors `decision_strategy/services/strategy_interfaces.py`.  Defines
the public contract for pluggable policies, evaluators, and the
in-memory result returned by `ApprovalEngine.evaluate(...)`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..constants import (
    ApprovalActorRole,
    ApprovalOutcome,
    ApprovalRequirementMode,
    ApprovalState,
    ApprovalType,
)


# ─────────────────────────────────────────────────────────────────────
#  Policy descriptor interface
# ─────────────────────────────────────────────────────────────────────
class IApprovalPolicy:
    """
    Implementations describe ONE approval policy.

    A policy answers three questions for a given context:
      1. Is approval required?
      2. Which approvers / roles are required?
      3. Should the request be auto-approved / auto-rejected?
    """

    #: Stable identifier (e.g. "default", "high_risk_security").
    name: str = ""
    #: monotonically increasing — used for optimistic locking.
    version: int = 1
    #: Human-readable summary.
    description: str = ""

    def is_applicable(self, context: Any) -> bool:
        """Return True if this policy applies to the given context."""
        return True

    def requires_approval(self, context: Any) -> bool:
        """Return True if at least one approver is required."""
        raise NotImplementedError

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        """Return the ordered list of approver roles this policy mandates."""
        raise NotImplementedError

    def evaluate(self, context: Any) -> "ApprovalPolicyResult":
        """Compute the deterministic policy verdict + reasons."""
        raise NotImplementedError


@dataclass
class ApprovalPolicyResult:
    """Deterministic verdict returned by `IApprovalPolicy.evaluate`."""
    requires_approval: bool
    required_roles: List[ApprovalActorRole] = field(default_factory=list)
    requirement_mode: ApprovalRequirementMode = ApprovalRequirementMode.SINGLE
    auto_approve: bool = False
    auto_reject: bool = False
    risk_score: float = 0.0
    criticality_score: float = 0.0
    confidence: float = 0.0
    reasons: List[Tuple[str, str]] = field(default_factory=list)  # (code, description)
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────
#  Registry contract
# ─────────────────────────────────────────────────────────────────────
class IApprovalRegistry:
    """Mutable map of policy name → descriptor."""
    def register(self, policy: IApprovalPolicy) -> None: ...
    def get(self, name: str) -> Optional[IApprovalPolicy]: ...
    def all(self) -> Dict[str, IApprovalPolicy]: ...
    def applicable(self, context: Any) -> List[IApprovalPolicy]: ...


# ─────────────────────────────────────────────────────────────────────
#  Evaluator contract
# ─────────────────────────────────────────────────────────────────────
class IApprovalEvaluator:
    """One pluggable factor evaluator used by the policy engine."""
    name: str = ""

    def evaluate(self, context: Any) -> float:
        """Return a normalized [0.0, 1.0] score for this factor."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────
#  Resolver contract
# ─────────────────────────────────────────────────────────────────────
class IApprovalResolver:
    """Resolves which policies apply + aggregates the verdict."""
    def resolve(self, context: Any) -> List[IApprovalPolicy]: ...
    def aggregate(self, results: List[ApprovalPolicyResult]) -> ApprovalPolicyResult: ...


# ─────────────────────────────────────────────────────────────────────
#  Validator contract
# ─────────────────────────────────────────────────────────────────────
class IApprovalValidator:
    """Returns a list of error codes; [] means valid."""
    def validate(self, request: Any, context: Any) -> List[str]: ...


# ─────────────────────────────────────────────────────────────────────
#  Repository contract
# ─────────────────────────────────────────────────────────────────────
class IApprovalRepository:
    """Persistence boundary — implementation lives in approval_repository.py."""
    async def save_request(self, request: Any) -> Any: ...
    async def get_request(self, request_id: str) -> Optional[Any]: ...
    async def list_requests(self, tenant_id: str, **filters: Any) -> List[Any]: ...
    async def save_policy(self, policy: Any) -> Any: ...
    async def list_policies(self, tenant_id: str) -> List[Any]: ...
    async def save_evaluation(self, result: "ApprovalEvaluationResult") -> Any: ...


# ─────────────────────────────────────────────────────────────────────
#  Lifecycle manager contract
# ─────────────────────────────────────────────────────────────────────
class IApprovalLifecycleManager:
    """Transitions ApprovalState with validity checks."""
    def can_transition(self, from_state: ApprovalState, to_state: ApprovalState) -> bool: ...
    async def transition(self, request_id: str, to_state: ApprovalState, *, changed_by: str, reason: Optional[str] = None) -> Any: ...


# ─────────────────────────────────────────────────────────────────────
#  Data containers (in-memory)
# ─────────────────────────────────────────────────────────────────────
@dataclass
class ApprovalRequirementSpec:
    """An in-memory spec for one required approver slot."""
    role: ApprovalActorRole
    sequence_order: int = 1
    is_mandatory: bool = True
    description: Optional[str] = None


@dataclass
class ApprovalCandidateData:
    """Aggregated in-memory view of an ApprovalRequest candidate."""
    decision_id: str
    strategy_id: Optional[str]
    tenant_id: str
    approval_type: ApprovalType
    requirement_mode: ApprovalRequirementMode
    requirements: List[ApprovalRequirementSpec] = field(default_factory=list)
    reasons: List[Tuple[str, str]] = field(default_factory=list)
    constraints: List[Tuple[str, bool, str]] = field(default_factory=list)  # (type, is_met, details)
    evidence: List[Tuple[str, str]] = field(default_factory=list)           # (type, value)
    metadata: List[Tuple[str, Any]] = field(default_factory=list)           # (key, scalar value)
    risk_score: float = 0.0
    criticality_score: float = 0.0
    composite_score: float = 0.0
    confidence: float = 0.0
    requires_approval: bool = True
    auto_approve: bool = False
    auto_reject: bool = False
    is_valid: bool = True
    rejection_reason: Optional[str] = None
    business_justification: Optional[str] = None
    technical_justification: Optional[str] = None
    is_emergency: bool = False
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None


@dataclass
class ApprovalEvaluationResult:
    """Final result of one evaluation run by `ApprovalEngine.evaluate`."""
    tenant_id: str
    decision_id: str
    strategy_id: Optional[str]
    candidate: Optional[ApprovalCandidateData]
    candidates: List[ApprovalCandidateData] = field(default_factory=list)
    ranking_stable: bool = True
    evaluation_duration_ms: int = 0
    winning_request_id: Optional[str] = None  # populated by the pipeline after persistence


__all__ = [
    "IApprovalPolicy",
    "IApprovalRegistry",
    "IApprovalEvaluator",
    "IApprovalResolver",
    "IApprovalValidator",
    "IApprovalRepository",
    "IApprovalLifecycleManager",
    "ApprovalPolicyResult",
    "ApprovalRequirementSpec",
    "ApprovalCandidateData",
    "ApprovalEvaluationResult",
]
