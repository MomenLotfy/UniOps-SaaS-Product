from __future__ import annotations
from typing import Any, Dict, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.investigation import InvestigationSession, InvestigationBookmark, SavedQuery
from app.schemas.investigation import InvestigationSessionSchema, InvestigationSessionCreate, InvestigationSessionUpdate
from app.utils.logger import logger
import uuid

class SessionManager:
    """
    Handles the persistence and lifecycle of investigation sessions.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_session(self, tenant_id: str, user_id: str, data: InvestigationSessionCreate) -> InvestigationSessionSchema:
        """
        Creates a new investigation session.
        """
        session = InvestigationSession(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            name=data.name,
            current_context=data.current_context
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return InvestigationSessionSchema.model_validate(session)

    async def get_session(self, session_id: str, tenant_id: str) -> Optional[InvestigationSessionSchema]:
        """
        Retrieves a session by ID.
        """
        stmt = select(InvestigationSession).where(
            InvestigationSession.id == session_id,
            InvestigationSession.tenant_id == tenant_id
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            return None

        return InvestigationSessionSchema.model_validate(session)

    async def update_session_context(self, session_id: str, tenant_id: str, context: Dict[str, Any]) -> InvestigationSessionSchema:
        """
        Updates the current filters and context for a session.
        """
        stmt = (
            update(InvestigationSession)
            .where(InvestigationSession.id == session_id, InvestigationSession.tenant_id == tenant_id)
            .values(current_context=context)
            .returning(InvestigationSession)
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError("Session not found")

        await self.db.commit()
        return InvestigationSessionSchema.model_validate(session)

    async def add_bookmark(self, session_id: str, tenant_id: str, bookmark_data: Any) -> InvestigationBookmarkSchema:
        """
        Adds a bookmark to a session.
        """
        bookmark = InvestigationBookmark(
            id=str(uuid.uuid4()),
            session_id=session_id,
            tenant_id=tenant_id,
            entity_type=bookmark_data.entity_type,
            entity_id=bookmark_data.entity_id,
            label=bookmark_data.label,
            context_snapshot=bookmark_data.context_snapshot
        )
        self.db.add(bookmark)
        await self.db.commit()
        await self.db.refresh(bookmark)
        return InvestigationBookmarkSchema.model_validate(bookmark)
