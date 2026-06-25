from __future__ import annotations
"""Repository Risk Rating API endpoints."""
from typing import Optional
from fastapi import APIRouter, Query
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.services.risk_service import RiskService
from app.core.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=APIResponse)
async def list_risk_ratings(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """
    List risk ratings for all repositories, sorted by risk score descending
    (critical repositories first).
    """
    svc  = RiskService(db)
    data = await svc.list_risk_ratings(tenant_id)
    return APIResponse(data=data)


@router.get("/{repo_id}", response_model=APIResponse)
async def get_risk_rating(
    repo_id:      str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """Get the risk rating for a single repository."""
    svc  = RiskService(db)
    data = await svc.get_risk_rating(tenant_id, repo_id)
    if not data:
        raise NotFoundError("Risk rating", repo_id)
    return APIResponse(data=data)
