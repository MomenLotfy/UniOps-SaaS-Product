from __future__ import annotations
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.investigation.query.planner import QueryPlanner
from app.services.investigation.query.optimizer import QueryOptimizer
from app.services.investigation.query.executor import QueryExecutor
from app.services.investigation.search.engine import SearchEngine
from app.services.investigation.timeline.engine import TimelineEngine
from app.services.investigation.correlation.engine import CorrelationEngine
from app.services.investigation.filter.engine import FilterEngine

from app.schemas.investigation import InvestigationQuery, InvestigationResult, SearchRequest, SearchResponse, TimelineRequest, TimelineResponse, CorrelationRequest, CorrelationResponse

class InvestigationEngine:
    """
    The central orchestrator for the Security Investigation Platform.
    It delegates specialized reasoning to the sub-engines.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

        # Core Sub-Engines
        self.filter_engine = FilterEngine()
        self.search_engine = SearchEngine(db_session)
        self.timeline_engine = TimelineEngine(db_session)
        self.correlation_engine = CorrelationEngine(db_session)

        # Query Pipeline
        self.planner = QueryPlanner()
        self.optimizer = QueryOptimizer()
        self.executor = QueryExecutor(db_session, self.filter_engine, self.search_engine)

    async def run_query(self, query: InvestigationQuery) -> InvestigationResult:
        """
        Deterministic execution of a complex investigation query.
        """
        # 1. Plan the query
        plan = self.planner.plan(query)

        # 2. Optimize the plan
        optimized_plan = self.optimizer.optimize(plan)

        # 3. Execute and return results
        return await self.executor.execute(optimized_plan, query.target_entity)

    async def run_search(self, request: SearchRequest) -> SearchResponse:
        """
        Deterministic search across multiple entities.
        """
        hits = await self.search_engine.search(
            query=request.query,
            entity_types=request.entity_types,
            limit=request.limit,
            offset=request.offset
        )

        suggestions = await self.search_engine.get_suggestions(request.query)

        return SearchResponse(
            hits=hits,
            total_hits=len(hits),
            suggestions=suggestions,
            execution_time_ms=0.0 # Real timer would be here
        )

    async def run_timeline(self, request: TimelineRequest) -> TimelineResponse:
        """
        Reconstructs the timeline for a specific entity.
        """
        return await self.timeline_engine.get_entity_timeline(
            request.entity_id,
            request.entity_type,
            request.start_time,
            request.end_time,
            request.event_types
        )

    async def run_correlation(self, request: CorrelationRequest) -> CorrelationResponse:
        """
        Finds deterministic links between entities.
        """
        return await self.correlation_engine.correlate(
            request.source_entity_id,
            request.source_entity_type,
            request.target_entity_id,
            request.target_entity_type,
            request.depth
        )
