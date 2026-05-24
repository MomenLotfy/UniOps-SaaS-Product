from __future__ import annotations
"""Alerts API — alert management, bulk operations, and stats."""
from typing import Optional
from fastapi import APIRouter, Query
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.alert import AlertResponse, AlertUpdate, AlertStats
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.alert_service import AlertService

router = APIRouter()


@router.get("", response_model=APIResponse[PaginatedResponse])
async def list_alerts(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_read: Optional[bool] = Query(None),
):
    svc = AlertService(db)
    result = await svc.list(tenant_id, page, page_size, severity, status, category, is_read)
    return APIResponse(data=result)


@router.get("/stats", response_model=APIResponse[AlertStats])
async def get_alert_stats(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = AlertService(db)
    stats = await svc.get_stats(tenant_id)
    return APIResponse(data=stats)


@router.get("/{alert_id}", response_model=APIResponse[AlertResponse])
async def get_alert(alert_id: str, current_user: CurrentUser, db: DBSession):
    svc = AlertService(db)
    alert = await svc.get_by_id(alert_id)
    return APIResponse(data=alert)


@router.patch("/{alert_id}", response_model=APIResponse[AlertResponse])
async def update_alert(alert_id: str, data: AlertUpdate, current_user: CurrentUser, db: DBSession):
    svc = AlertService(db)
    alert = await svc.update(alert_id, data)
    return APIResponse(data=alert)


@router.post("/bulk/mark-read")
async def mark_all_read(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = AlertService(db)
    count = await svc.mark_all_read(tenant_id)
    return APIResponse(data={"updated": count}, message=f"{count} alerts marked as read")


@router.post("/bulk/resolve")
async def resolve_all(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    category: Optional[str] = Query(None),
):
    svc = AlertService(db)
    count = await svc.resolve_all(tenant_id, category)
    return APIResponse(data={"resolved": count}, message=f"{count} alerts resolved")
