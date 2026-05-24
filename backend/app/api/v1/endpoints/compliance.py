from __future__ import annotations
"""Compliance API — security framework compliance scoring."""
from fastapi import APIRouter
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.services.security_service import SecurityService

router = APIRouter()


@router.get("")
async def list_compliance(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = SecurityService(db)
    items = await svc.list_compliance(tenant_id)
    return APIResponse(data=items)


@router.get("/score")
async def get_compliance_score(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = SecurityService(db)
    score = await svc.get_compliance_score(tenant_id)
    return APIResponse(data=score)
