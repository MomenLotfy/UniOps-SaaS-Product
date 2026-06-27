"""
Strategy Candidate Builder.

Glue between the Resolver + Factory + Validator + ScoringEngine.  The
Pipeline calls `build_candidates(...)` once and receives a fully
populated list of candidates ready for ranking.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .strategy_interfaces import StrategyCandidateData
from .strategy_factory import DecisionStrategyFactory
from .strategy_resolver import DecisionStrategyResolver
from .strategy_validator import DecisionStrategyValidator
from .strategy_scoring_engine import StrategyScoringEngine


class StrategyCandidateBuilder:
    def __init__(
        self,
        resolver: DecisionStrategyResolver,
        factory: DecisionStrategyFactory,
        validator: DecisionStrategyValidator,
        scoring_engine: StrategyScoringEngine,
    ) -> None:
        self._resolver      = resolver
        self._factory       = factory
        self._validator     = validator
        self._scoring       = scoring_engine

    def build_candidates(
        self,
        decision: Any,
        context: Any,
        statistics: Dict,
    ) -> List[StrategyCandidateData]:
        descriptors = self._resolver.resolve(decision, context)
        candidates: List[StrategyCandidateData] = []

        for desc in descriptors:
            cand = self._factory.build_candidate(desc, decision, context)
            # Validate first (mutates is_valid + rejection_reason)
            self._validator.validate(cand)
            # Always score, even invalid candidates — useful for audit
            self._scoring.score(cand, decision, context, statistics)
            candidates.append(cand)

        return candidates