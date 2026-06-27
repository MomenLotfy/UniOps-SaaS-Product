"""
Decision Strategy Selector.

Picks the WINNING candidate from a ranked list.

Selection rules (deterministic):
    1. If at least one valid candidate exists, return the top-ranked one.
    2. Otherwise, fall back to NO_ACTION (always applicable).
    3. If NO_ACTION is also absent (should never happen), return None.

The selector does NOT mutate candidates; it only picks.
"""
from __future__ import annotations

from typing import List, Optional

from ..constants import StrategyType
from .strategy_interfaces import IStrategySelector, StrategyCandidateData


class DecisionStrategySelector(IStrategySelector):
    def select(self, ranked: List[StrategyCandidateData]) -> Optional[StrategyCandidateData]:
        # 1. First valid candidate (highest-ranked)
        for c in ranked:
            if c.is_valid:
                return c

        # 2. NO_ACTION fallback
        for c in ranked:
            if c.candidate_type == StrategyType.NO_ACTION:
                return c

        return None