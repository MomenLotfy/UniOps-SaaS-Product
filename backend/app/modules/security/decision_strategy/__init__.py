"""
Decision Strategy Engine (Module 0 / Part 4).

Deterministic selection of a remediation *strategy* — not the
remediation itself.  Produces ranked candidates with multi-dimension
scoring and an audit trail.

Public entry points:
  - `DecisionStrategyEngine.evaluate(...)`  → in-memory evaluation
  - `StrategyEvaluationPipeline.run(...)`   → evaluation + persistence
  - `DecisionStrategyService`               → read-only API facade
"""
from __future__ import annotations

from .constants import (
    FINAL_RESULT_TO_STRATEGY_HINTS,
    RejectionReason,
    SCORING_WEIGHTS,
    STRATEGY_CACHE_TTL_SECONDS,
    StrategyPipelineStage,
    StrategyState,
    StrategyType,
    VALID_STRATEGY_TRANSITIONS,
)
from .models.strategy import (
    DecisionStrategy,
    StrategyCandidate,
    StrategyConstraint,
    StrategyEvaluation,
    StrategyEvidence,
    StrategyHistory,
    StrategyMetadata,
    StrategyRanking,
    StrategyReason,
    StrategyRequirement,
    StrategyScore,
    StrategyStatistics,
    StrategyVersion,
)
from .services import (
    DecisionStrategyCache,
    DecisionStrategyComparator,
    DecisionStrategyEngine,
    DecisionStrategyFactory,
    DecisionStrategyLifecycleManager,
    DecisionStrategyManager,
    DecisionStrategyRegistry,
    DecisionStrategyRepository,
    DecisionStrategyResolver,
    DecisionStrategySelector,
    DecisionStrategyService,
    DecisionStrategyStatisticsService,
    DecisionStrategyValidator,
    StrategyCandidateBuilder,
    StrategyEvaluationPipeline,
    StrategyEvaluationResult,
    StrategyRankingEngine,
    StrategyScoringEngine,
    bootstrap_default_strategies,
)

__all__ = [
    "DecisionStrategy",
    "DecisionStrategyCache",
    "DecisionStrategyComparator",
    "DecisionStrategyEngine",
    "DecisionStrategyFactory",
    "DecisionStrategyLifecycleManager",
    "DecisionStrategyManager",
    "DecisionStrategyRegistry",
    "DecisionStrategyRepository",
    "DecisionStrategyResolver",
    "DecisionStrategySelector",
    "DecisionStrategyService",
    "DecisionStrategyStatisticsService",
    "DecisionStrategyValidator",
    "FINAL_RESULT_TO_STRATEGY_HINTS",
    "RejectionReason",
    "SCORING_WEIGHTS",
    "STRATEGY_CACHE_TTL_SECONDS",
    "StrategyCandidate",
    "StrategyCandidateBuilder",
    "StrategyConstraint",
    "StrategyEvaluation",
    "StrategyEvidence",
    "StrategyEvaluationPipeline",
    "StrategyEvaluationResult",
    "StrategyHistory",
    "StrategyMetadata",
    "StrategyRanking",
    "StrategyRankingEngine",
    "StrategyReason",
    "StrategyRequirement",
    "StrategyScore",
    "StrategyPipelineStage",
    "StrategyScoringEngine",
    "StrategyState",
    "StrategyStatistics",
    "StrategyType",
    "StrategyVersion",
    "VALID_STRATEGY_TRANSITIONS",
    "bootstrap_default_strategies",
]