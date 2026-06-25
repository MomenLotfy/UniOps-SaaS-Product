"""SLA tracking API — critical=24h, high=7d, medium=30d."""
from __future__ import annotations
from fastapi import APIRouter, Query
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.services.sla_service import SLAService

router = APIRouter()


@router.get("/summary", response_model=APIResponse)
async def get_sla_summary(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """SLA dashboard: total open, overdue counts, due soon, breakdown by severity."""
    svc  = SLAService(db)
    data = await svc.get_summary(tenant_id)
    return APIResponse(data=data)


@router.get("/findings", response_model=APIResponse)
async def list_sla_findings(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    severity:     str | None = None,
    status:       str | None = None,
    entity_type:  str | None = None,
    overdue_only: bool = False,
    limit:        int  = Query(100, le=500),
    offset:       int  = 0,
):
    """List all findings with SLA metadata — remaining time, overdue flag, owner, team."""
    svc  = SLAService(db)
    data = await svc.list_slas(
        tenant_id=tenant_id, severity=severity, status=status,
        overdue_only=overdue_only, entity_type=entity_type,
        limit=limit, offset=offset,
    )
    return APIResponse(data=data)


@router.post("/sync", response_model=APIResponse)
async def sync_slas(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """Pull all open threats+vulns and upsert SLA records. Refreshes overdue flags."""
    svc = SLAService(db)
    result = await svc.sync_findings(tenant_id)
    await svc.refresh_overdue(tenant_id)
    return APIResponse(data=result, message="SLA records synced")


@router.post("/refresh-overdue", response_model=APIResponse)
async def refresh_overdue(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """Recompute overdue flags for all open SLA records."""
    svc   = SLAService(db)
    count = await svc.refresh_overdue(tenant_id)
    return APIResponse(data={"updated": count}, message=f"{count} SLA records marked overdue")
