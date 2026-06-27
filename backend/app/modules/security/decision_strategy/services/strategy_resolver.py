"""
Decision Strategy Resolver.

Wraps the Registry's `discover(...)` and applies final-result hints to
nudge the candidate ordering.  Does NOT validate, score, or rank — those
are separate concerns.
"""
from __future__ import annotations

from typing import Any, List

from ..constants import FINAL_RESULT_TO_STRATEGY_HINTS
from .strategy_interfaces import IStrategyDescriptor


class DecisionStrategyResolver:
    """Picks the set of applicable strategy descriptors for a Decision."""

    def __init__(self, registry) -> None:
        self._registry = registry

    def resolve(
        self,
        decision: Any,
        context: Any,
    ) -> List[IStrategyDescriptor]:
        """
        Returns applicable descriptors, with `final_result`-hinted
        strategies ordered FIRST.  Within each group, the registry
        iteration order is preserved (deterministic).
        """
        applicable = self._registry.discover(decision, context)

        # Determine hint set from decision.final_result (defensive).
        final_result = getattr(decision, "final_result", None) or ""
        hinted_types = set(FINAL_RESULT_TO_STRATEGY_HINTS.get(final_result, []))

        hinted   = [d for d in applicable if d.strategy_type in hinted_types]
        unhinted = [d for d in applicable if d.strategy_type not in hinted_types]

        return hinted + unhinted