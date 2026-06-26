from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.schemas.investigation import InvestigationQuery

class QueryPlanStep:
    def __init__(self, engine_type: str, params: Dict[str, Any], priority: int = 0):
        self.engine_type = engine_type # 'filter', 'search', 'graph', 'correlation'
        self.params = params
        self.priority = priority

class QueryPlanner:
    """
    The QueryPlanner analyzes an investigation query and breaks it down into
    a sequence of deterministic execution steps.
    """

    def plan(self, query: InvestigationQuery) -> List[QueryPlanStep]:
        """
        Transforms a high-level query into an execution plan.
        """
        steps = []

        # 1. Handle Search Terms first (most restrictive)
        if query.search_term:
            steps.append(QueryPlanStep(
                engine_type="search",
                params={
                    "query": query.search_term,
                    "target_entity": query.target_entity,
                    "limit": query.limit,
                    "offset": query.offset
                },
                priority=10
            ))

        # 2. Handle Filters
        if query.filters:
            steps.append(QueryPlanStep(
                engine_type="filter",
                params={
                    "target_entity": query.target_entity,
                    "filters": query.filters,
                    "limit": query.limit,
                    "offset": query.offset,
                    "sort_by": query.sort_by,
                    "sort_direction": query.sort_direction
                },
                priority=5
            ))

        # 3. Handle Target Entity basic lookup if no filters/search
        if not query.search_term and not query.filters:
            steps.append(QueryPlanStep(
                engine_type="filter",
                params={
                    "target_entity": query.target_entity,
                    "filters": {},
                    "limit": query.limit,
                    "offset": query.offset,
                    "sort_by": query.sort_by,
                    "sort_direction": query.sort_direction
                },
                priority=1
            ))

        return steps
