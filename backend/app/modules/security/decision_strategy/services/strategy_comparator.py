"""
Decision Strategy Comparator.

Pure deterministic comparator.  Used by the RankingEngine's
`functools.cmp_to_key` to produce a totally-ordered list of candidates
without any randomness.

Tiebreaker order (strict):
    1. composite_score     DESC
    2. feasibility_score   DESC
    3. confidence proxy    DESC  (here: 1 - is_rejected)
    4. strategy_type       ASC   (alphabetical on enum value)
"""
from __future__ import annotations

from .strategy_interfaces import IStrategyComparator, StrategyCandidateData


class DecisionStrategyComparator(IStrategyComparator):
    def compare(self, a: StrategyCandidateData, b: StrategyCandidateData) -> int:
        # 1. composite_score DESC
        if a.composite_score != b.composite_score:
            return -1 if a.composite_score > b.composite_score else 1

        # 2. feasibility_score DESC
        if a.feasibility_score != b.feasibility_score:
            return -1 if a.feasibility_score > b.feasibility_score else 1

        # 3. validity proxy DESC
        if a.is_valid != b.is_valid:
            return -1 if a.is_valid else 1

        # 4. strategy_type ASC (alphabetical)
        return (a.candidate_type.value > b.candidate_type.value) - (
            a.candidate_type.value < b.candidate_type.value
        )