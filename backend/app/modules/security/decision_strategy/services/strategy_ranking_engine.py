"""
Decision Strategy Ranking Engine.

Uses `DecisionStrategyComparator` via `functools.cmp_to_key` to produce
a deterministic, fully-ordered list of candidates.  Assigns a 1-based
`rank` to each candidate.

INVALID candidates are ranked AFTER all valid ones — they appear last
in the list with `rank=None` (they are kept for audit, not for selection).
"""
from __future__ import annotations

from functools import cmp_to_key
from typing import List

from .strategy_interfaces import IStrategyRankingEngine, StrategyCandidateData
from .strategy_comparator import DecisionStrategyComparator


class StrategyRankingEngine(IStrategyRankingEngine):
    def __init__(self, comparator: DecisionStrategyComparator = None):
        self._cmp = comparator or DecisionStrategyComparator()

    def rank(self, candidates: List[StrategyCandidateData]) -> List[StrategyCandidateData]:
        valid   = [c for c in candidates if c.is_valid]
        invalid = [c for c in candidates if not c.is_valid]

        valid_sorted   = sorted(valid,   key=cmp_to_key(self._cmp.compare))
        # Invalid candidates keep their original registry order (deterministic).
        invalid_sorted = list(invalid)

        # 1-based rank for valid candidates
        for i, c in enumerate(valid_sorted, start=1):
            c.rank = i
        for c in invalid_sorted:
            c.rank = None

        return valid_sorted + invalid_sorted