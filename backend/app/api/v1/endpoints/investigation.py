from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query as FastQuery
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any

from app.api.deps import get_db, CurrentUser, TenantID
from app.services.investigation.service import InvestigationService
from app.schemas.investigation import (
    InvestigationQuery, InvestigationResult, SearchRequest, SearchResponse,
    TimelineRequest, TimelineResponse, CorrelationRequest, CorrelationResponse,
    InvestigationSessionSchema, InvestigationSessionCreate, InvestigationBookmarkSchema, InvestigationBookmarkCreate
)

router = APIRouter()

@router.post("/query", response_model=InvestigationResult)
async def execute_query(
    query: InvestigationQuery,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: AsyncSession = Depends(get_db)
):
    """Executes a deterministic investigation query."""
    service = InvestigationService(db)
    return await service.query(query)

@router.post("/search", response_model=SearchResponse)
async def search_entities(
    request: SearchRequest,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: AsyncSession = Depends(get_db)
):
    """Performs a deterministic search across security entities."""
    service = InvestigationService(db)
    return await service.search(request)

@router.post("/timeline", response_model=TimelineResponse)
async def get_timeline(
    request: TimelineRequest,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: AsyncSession = Depends(get_db)
):
    """Retrieves the historical timeline for an entity."""
    service = InvestigationService(db)
    return await service.get_timeline(request)

@router.post("/correlation", response_model=CorrelationResponse)
async def get_correlation(
    request: CorrelationRequest,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: AsyncSession = Depends(get_db)
):
    """Finds deterministic correlations between entities."""
    service = InvestigationService(db)
    return await service.correlate(request)

@router.post("/sessions", response_model=InvestigationSessionSchema)
async def create_session(
    data: InvestigationSessionCreate,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: AsyncSession = Depends(get_db)
):
    """Starts a new investigation session."""
    service = InvestigationService(db)
    user_id = current_user.get("user_id", current_user.get("sub", "unknown"))
    return await service.create_session(tenant_id, user_id, data)

@router.get("/sessions/{session_id}", response_model=InvestigationSessionSchema)
async def get_session(
    session_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: AsyncSession = Depends(get_db)
):
    """Retrieves a session's current state."""
    service = InvestigationService(db)
    session = await service.get_session(session_id, tenant_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/sessions/{session_id}/bookmarks", response_model=InvestigationBookmarkSchema)
async def add_bookmark(
    session_id: str,
    bookmark: InvestigationBookmarkCreate,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: AsyncSession = Depends(get_db)
):
    """Adds a bookmark to the investigation session."""
    service = InvestigationService(db)
    return await service.add_bookmark(session_id, tenant_id, bookmark)
