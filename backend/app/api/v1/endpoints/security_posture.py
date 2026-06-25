from __future__ import annotations
"""Security Posture API — compute and retrieve security posture scores over time."""
from typing import Optional
from fastapi import APIRouter, Query
from app.api.deps import SecurityReadUser, AuditReadUser, TenantID, DBSession
from app.schemas.security_posture import SecurityPostureResponse, SecurityPostureSummary
from app.schemas.common import APIResponse
from app.services.security_posture_service import SecurityPostureService
from app.utils.logger import logger

router = APIRouter()


@router.get("/summary", response_model=APIResponse[SecurityPostureSummary])
async def get_posture_summary(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    logger.info(f"[posture:summary] tenant={tenant_id[:8]}")
    svc = SecurityPostureService(db)
    summary = await svc.get_summary(tenant_id)
    return APIResponse(data=summary)


@router.get("/history", response_model=APIResponse)
async def get_posture_history(
    current_user: AuditReadUser,
    tenant_id: TenantID,
    db: DBSession,
    days: int = Query(30, ge=7, le=365),
):
    logger.info(f"[posture:history] tenant={tenant_id[:8]} days={days}")
    svc = SecurityPostureService(db)
    history = await svc.get_history(tenant_id, days=days)
    return APIResponse(data=history)


@router.get("/dashboard", response_model=APIResponse)
async def get_posture_dashboard(
    current_user: SecurityReadUser,
    tenant_id:    TenantID,
    db:           DBSession,
    days: int = Query(30, ge=7, le=90),
):
    """Security Posture Dashboard — 5 real scores + 7/30/90d trends + 3 charts."""
    logger.info(f"[posture:dashboard] tenant={tenant_id[:8]} days={days}")
    svc  = SecurityPostureService(db)
    data = await svc.get_dashboard(tenant_id, days=days)
    return APIResponse(data=data)


@router.post("/snapshot", response_model=APIResponse[SecurityPostureResponse])
async def record_posture_snapshot(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Compute and persist the current posture score. Called by scheduler and on demand."""
    logger.info(f"[posture:snapshot] tenant={tenant_id[:8]}")
    svc = SecurityPostureService(db)
    snapshot = await svc.record_snapshot(tenant_id)
    return APIResponse(data=snapshot, message="Posture snapshot recorded")
