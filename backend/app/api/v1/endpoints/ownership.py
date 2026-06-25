"""Ownership management API — owner/team/department for security entities."""
from __future__ import annotations
from fastapi import APIRouter, Query
from pydantic import BaseModel as PydanticModel
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.services.ownership_service import OwnershipService

router = APIRouter()


class OwnershipUpdate(PydanticModel):
    entity_type: str   # threat | vulnerability | repository | asset
    entity_id:   str
    owner:       str | None = None
    team:        str | None = None
    department:  str | None = None


@router.get("", response_model=APIResponse)
async def list_ownership(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    entity_type:  str | None = None,
    owner:        str | None = None,
    team:         str | None = None,
    department:   str | None = None,
    limit:        int = Query(100, le=500),
    offset:       int = 0,
):
    """List entities with their ownership metadata, filterable by owner/team/department."""
    svc  = OwnershipService(db)
    data = await svc.list_ownership(
        tenant_id=tenant_id, entity_type=entity_type,
        owner=owner, team=team, department=department,
        limit=limit, offset=offset,
    )
    return APIResponse(data=data)


@router.get("/{entity_type}/{entity_id}", response_model=APIResponse)
async def get_ownership(
    entity_type:  str,
    entity_id:    str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    svc  = OwnershipService(db)
    data = await svc.get_ownership(tenant_id, entity_type, entity_id)
    return APIResponse(data=data)


@router.patch("/{entity_type}/{entity_id}", response_model=APIResponse)
async def set_ownership(
    entity_type:  str,
    entity_id:    str,
    body:         OwnershipUpdate,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """Set owner, team, and/or department for any security entity."""
    svc  = OwnershipService(db)
    data = await svc.set_ownership(
        tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
        owner=body.owner, team=body.team, department=body.department,
    )
    return APIResponse(data=data, message="Ownership updated")
