from __future__ import annotations
from typing import List
from .planner import QueryPlanStep

class QueryOptimizer:
    """
    The QueryOptimizer refines the execution plan to improve performance.
    Currently implements basic priority-based reordering.
    """

    def optimize(self, steps: List[QueryPlanStep]) -> List[QueryPlanStep]:
        """
        Optimizes the plan by sorting steps by their expected selectivity (priority).
        """
        # Sort steps by priority descending
        return sorted(steps, key=lambda x: x.priority, reverse=True)
