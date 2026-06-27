"""
Abstract interfaces and shared dataclasses for the Decision Strategy Engine.

Mirrors the style of decision_engine/services/policy_interfaces.py so that
the two engines feel like siblings rather than divergent designs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..constants import RejectionReason, StrategyState, StrategyType


# ─── Dataclasses (pure data, no ORM) ────────────────────────────────────────

@dataclass
class StrategyScoreBreakdown:
    """
    Per-dimension score for one candidate.

    `value`     — raw score in [0.0, 1.0]
    `weight`    — weight from constants.SCORING_WEIGHTS
    `rationale` — human-readable justification (for UI + audit)
    """
    dimension: str
    value: float
    weight: float
    rationale: str = ""

    @property
    def contribution(self) -> float:
        return float(self.value) * float(self.weight)


@dataclass
class _StrategyCandidateMeta:
    """Lightweight metadata container for constraints / requirements."""
    type: str
    description: str
    is_met: bool = True
    required: bool = True
    satisfied: bool = True


@dataclass
class _StrategyReasonMeta:
    reason_code: str
    description: str
    impact: str = "MEDIUM"


@dataclass
class StrategyCandidateData:
    """
    In-memory representation of one strategy candidate.

    NOT an ORM row — that's `models.StrategyCandidate`.  This is the
    pipeline-friendly container used between Discovery → Selection.
    """
    candidate_type: StrategyType
    tenant_id: str = "default"
    decision_id: str = ""
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None

    is_valid: bool = True
    rejection_reason: Optional[str] = None
    rejection_details: Optional[str] = None

    # Scoring (filled in by StrategyScoringEngine)
    scores: List[StrategyScoreBreakdown] = field(default_factory=list)
    feasibility_score: float = 0.0
    risk_score: float = 0.0
    confidence: float = 0.0
    composite_score: float = 0.0

    # Ranking (assigned by StrategyRankingEngine)
    rank: Optional[int] = None

    # Constraints / requirements / reasons
    constraints: List[_StrategyCandidateMeta]  = field(default_factory=list)
    requirements: List[_StrategyCandidateMeta] = field(default_factory=list)
    reasons:     List[_StrategyReasonMeta]     = field(default_factory=list)

    # Static metadata (filled in by StrategyCandidateBuilder)
    expected_downtime_min: int = 0
    requires_human_approval: bool = False
    is_reversible: bool = True

    # Justifications
    business_justification: Optional[str] = None
    technical_justification: Optional[str] = None
    selection_reason: Optional[str] = None

    # Pipeline helpers
    priority: int = 100
    decision: Any = None  # back-pointer to the source Decision

    def add_score(self, breakdown: StrategyScoreBreakdown) -> None:
        self.scores.append(breakdown)

    @property
    def score_breakdown(self) -> List[StrategyScoreBreakdown]:
        return self.scores


@dataclass
class StrategyEvaluationResult:
    """
    The output of one full StrategyEvaluationPipeline.run(...) call.

    Carries the chosen DecisionStrategy plus every considered candidate
    so callers (UI, audit, statistics) can render the full picture.
    """
    tenant_id: str
    decision_id: str
    candidates: List[StrategyCandidateData] = field(default_factory=list)
    winner: Optional[StrategyCandidateData] = None
    winning_strategy_id: Optional[str] = None
    ranking_stable: bool = True
    evaluation_duration_ms: int = 0


# ─── Interfaces (ABC) ───────────────────────────────────────────────────────

class IStrategyDescriptor(ABC):
    """
    Plugin contract for a single strategy type.

    New strategies MUST be implemented as descriptors and registered via
    `DecisionStrategyRegistry.register(...)`.  The pipeline itself is
    agnostic to specific strategies — it iterates the registry.
    """
    strategy_type: StrategyType

    @abstractmethod
    def applicable(self, decision: Any, context: Any) -> bool:
        """Return True if this strategy is worth considering at all."""

    @abstractmethod
    def hard_constraints(self, decision: Any, context: Any) -> List[Dict[str, Any]]:
        """
        Return hard constraints.  Each constraint is a dict:
            {"type": str, "is_met": bool, "details": str}
        If ANY constraint is unmet, the candidate is rejected.
        """

    @abstractmethod
    def base_requirements(self, decision: Any, context: Any) -> List[Dict[str, Any]]:
        """
        Return non-fatal requirements (e.g. downtime window).  Used for
        downstream execution, not for rejection.
        """


class IStrategyRegistry(ABC):
    @abstractmethod
    def register(self, strategy_type: StrategyType, descriptor: IStrategyDescriptor) -> None: ...

    @abstractmethod
    def get(self, strategy_type: StrategyType) -> Optional[IStrategyDescriptor]: ...

    @abstractmethod
    def all(self) -> Dict[StrategyType, IStrategyDescriptor]: ...

    @abstractmethod
    def discover(self, decision: Any, context: Any) -> List[IStrategyDescriptor]:
        """Return descriptors whose `.applicable(...)` returns True."""


class IStrategyValidator(ABC):
    @abstractmethod
    def validate(self, candidate: StrategyCandidateData) -> StrategyCandidateData:
        """
        Mutates `candidate` in-place: sets `is_valid`, `rejection_reason`,
        populates `constraints`.  Returns the same object for chaining.
        """


class IStrategyScoringEngine(ABC):
    @abstractmethod
    def score(self, candidate: StrategyCandidateData, decision: Any, context: Any,
              statistics: Dict[str, Any]) -> StrategyCandidateData: ...


class IStrategyComparator(ABC):
    @abstractmethod
    def compare(self, a: StrategyCandidateData, b: StrategyCandidateData) -> int:
        """
        Deterministic comparator.
        Returns  -1 if a < b, 0 if equal, 1 if a > b.
        Tiebreakers MUST be deterministic (no randomness, no time.now()).
        """


class IStrategyRankingEngine(ABC):
    @abstractmethod
    def rank(self, candidates: List[StrategyCandidateData]) -> List[StrategyCandidateData]: ...


class IStrategySelector(ABC):
    @abstractmethod
    def select(self, ranked: List[StrategyCandidateData]) -> Optional[StrategyCandidateData]: ...


class IStrategyRepository(ABC):
    """Persistence boundary — production impl is SQLAlchemy."""

    @abstractmethod
    async def save_evaluation(self, result: StrategyEvaluationResult) -> Any: ...

    @abstractmethod
    async def get_by_id(self, strategy_id: str) -> Optional[Any]: ...

    @abstractmethod
    async def list_for_tenant(self, tenant_id: str,
                             state: Optional[StrategyState] = None,
                             strategy_type: Optional[StrategyType] = None,
                             limit: int = 100,
                             offset: int = 0) -> List[Any]: ...

    @abstractmethod
    async def list_history(self, strategy_id: str) -> List[Any]: ...

    @abstractmethod
    async def get_statistics(self, tenant_id: str) -> Dict[str, Any]: ...