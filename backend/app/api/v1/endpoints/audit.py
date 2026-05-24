from __future__ import annotations
"""Audit Logs API — query and export audit trail."""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Query
from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("", response_model=APIResponse[PaginatedResponse])
async def list_audit_logs(
    current_user: AdminUser, tenant_id: TenantID, db: DBSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
):
    svc = AuditService(db)
    result = await svc.list(
        tenant_id, page, page_size, user_id, action, resource, status, start_date, end_date
    )
    return APIResponse(data=result)


@router.get("/summary")
async def get_audit_summary(
    current_user: AdminUser, tenant_id: TenantID, db: DBSession,
    days: int = Query(7, ge=1, le=90),
):
    svc = AuditService(db)
    summary = await svc.get_activity_summary(tenant_id, days)
    return APIResponse(data=summary)
