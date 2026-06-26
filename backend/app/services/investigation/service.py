from __future__ import annotations
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.investigation.engine import InvestigationEngine
from app.services.investigation.session import SessionManager
from app.schemas.investigation import (
    InvestigationQuery, InvestigationResult, SearchRequest, SearchResponse,
    TimelineRequest, TimelineResponse, CorrelationRequest, CorrelationResponse,
    InvestigationSessionSchema, InvestigationSessionCreate, InvestigationBookmarkSchema, InvestigationBookmarkCreate
)

class InvestigationService:
    """
    The primary facade for the Security Investigation Platform.
    Coordinates session state and engine execution.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.engine = InvestigationEngine(db_session)
        self.sessions = SessionManager(db_session)

    async def query(self, query: InvestigationQuery) -> InvestigationResult:
        """
        Executes a deterministic investigation query.
        """
        return await self.engine.run_query(query)

    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Performs a deterministic search.
        """
        return await self.engine.run_search(request)

    async def get_timeline(self, request: TimelineRequest) -> TimelineResponse:
        """
        Retrieves the historical timeline for an entity.
        """
        return await self.engine.run_timeline(request)

    async def correlate(self, request: CorrelationRequest) -> CorrelationResponse:
        """
        Identifies deterministic correlations.
        """
        return await self.engine.run_correlation(request)

    # --- Session Management ---

    async def create_session(self, tenant_id: str, user_id: str, data: InvestigationSessionCreate) -> InvestigationSessionSchema:
        return await self.sessions.create_session(tenant_id, user_id, data)

    async def get_session(self, session_id: str, tenant_id: str) -> Optional[InvestigationSessionSchema]:
        return await self.sessions.get_session(session_id, tenant_id)

    async def update_session_context(self, session_id: str, tenant_id: str, context: Dict[str, Any]) -> InvestigationSessionSchema:
        return await self.sessions.update_session_context(session_id, tenant_id, context)

    async def add_bookmark(self, session_id: str, tenant_id: str, bookmark_data: InvestigationBookmarkCreate) -> InvestigationBookmarkSchema:
        return await self.sessions.add_bookmark(session_id, tenant_id, bookmark_data)
