from __future__ import annotations
"""Threats API — security threat management and real AWS Security Hub remediation."""
from typing import Optional
from fastapi import APIRouter, Query, Body
from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession
from app.schemas.threat import ThreatResponse, ThreatUpdate, ThreatStats, ThreatActionResult
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.security_service import SecurityService

router = APIRouter()


@router.get("", response_model=APIResponse[PaginatedResponse])
async def list_threats(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    svc = SecurityService(db)
    result = await svc.list_threats(tenant_id, page, page_size, severity, status, category)
    return APIResponse(data=result)


@router.get("/stats", response_model=APIResponse[ThreatStats])
async def get_threat_stats(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = SecurityService(db)
    stats = await svc.get_threat_stats(tenant_id)
    return APIResponse(data=stats)


@router.get("/{threat_id}", response_model=APIResponse[ThreatResponse])
async def get_threat(threat_id: str, current_user: CurrentUser, db: DBSession):
    svc = SecurityService(db)
    threat = await svc.get_threat(threat_id)
    return APIResponse(data=threat)


@router.patch("/{threat_id}", response_model=APIResponse[ThreatResponse])
async def update_threat(threat_id: str, data: ThreatUpdate, current_user: CurrentUser, db: DBSession):
    svc = SecurityService(db)
    threat = await svc.update_threat(threat_id, data)
    return APIResponse(data=threat)


@router.post("/{threat_id}/resolve", response_model=APIResponse[ThreatActionResult])
async def resolve_threat(
    threat_id: str,
    current_user: AdminUser,
    db: DBSession,
    note: str = Body(default="Resolved via UniOps Security Center", embed=True),
):
    """
    Resolve a threat in UniOps AND in AWS Security Hub (WorkflowStatus=RESOLVED).
    The finding is retained in Security Hub history for audit purposes.
    Requires: admin or security role.
    """
    svc = SecurityService(db)
    result = await svc.resolve_threat(threat_id, current_user["user_id"], note=note)
    return APIResponse(data=result, message=result.message)


@router.post("/{threat_id}/suppress", response_model=APIResponse[ThreatActionResult])
async def suppress_threat(
    threat_id: str,
    current_user: AdminUser,
    db: DBSession,
    reason: str = Body(default="TOLERATED", embed=True),
):
    """
    Suppress a threat — marks as false positive or accepted risk.
    In AWS Security Hub: WorkflowStatus = SUPPRESSED.
    reason: INTENDED | FALSE_POSITIVE | TOLERATED
    Requires: admin or security role.
    """
    svc = SecurityService(db)
    result = await svc.suppress_threat(threat_id, current_user["user_id"], reason=reason)
    return APIResponse(data=result, message=result.message)

