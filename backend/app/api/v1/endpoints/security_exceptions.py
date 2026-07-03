from __future__ import annotations
"""Security Exceptions API — manage exception requests with approval workflow."""
from typing import Optional
from fastapi import APIRouter, Query
from app.api.deps import (
    CurrentUser, SecurityReadUser, SecurityWriteUser, ComplianceUser,
    TenantID, DBSession,
)
from app.schemas.security_exception import (
    SecurityExceptionCreate, SecurityExceptionUpdate,
    SecurityExceptionReview, SecurityExceptionResponse,
)
from app.schemas.common import APIResponse
from app.services.security_exception_service import SecurityExceptionService
from app.utils.logger import logger

router = APIRouter()


@router.get("", response_model=APIResponse)
async def list_exceptions(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    exception_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None, description="Filter by finding_type / category"),
    severity: Optional[str] = Query(None, description="Filter by tags.severity (client-side compatible)"),
    policy_id: Optional[str] = Query(None),
    requested_by: Optional[str] = Query(None),
    approved_by: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Full-text search across title, ID, justification, owner"),
):
    logger.info(f"[exceptions:list] tenant={tenant_id[:8]} status={status} search={search}")
    svc = SecurityExceptionService(db)
    result = await svc.list_exceptions(
        tenant_id, page, page_size,
        status=status,
        exception_type=exception_type,
        category=category,
        severity=severity,
        policy_id=policy_id,
        requested_by=requested_by,
        approved_by=approved_by,
        search=search,
    )
    return APIResponse(data=result)


@router.post("", response_model=APIResponse[SecurityExceptionResponse])
async def create_exception(
    data: SecurityExceptionCreate,
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    logger.info(f"[exceptions:create] tenant={tenant_id[:8]} by={current_user['user_id'][:8]}")
    svc = SecurityExceptionService(db)
    exc = await svc.create_exception(tenant_id, data, current_user["user_id"])
    return APIResponse(data=exc, message="Exception request submitted")


@router.get("/stats", response_model=APIResponse)
async def get_exception_stats(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    svc = SecurityExceptionService(db)
    stats = await svc.get_stats(tenant_id)
    return APIResponse(data=stats)


@router.get("/{exception_id}", response_model=APIResponse[SecurityExceptionResponse])
async def get_exception(
    exception_id: str,
    current_user: SecurityReadUser,
    db: DBSession,
):
    svc = SecurityExceptionService(db)
    exc = await svc.get_exception(exception_id)
    return APIResponse(data=exc)


@router.patch("/{exception_id}", response_model=APIResponse[SecurityExceptionResponse])
async def update_exception(
    exception_id: str,
    data: SecurityExceptionUpdate,
    current_user: SecurityReadUser,
    db: DBSession,
):
    svc = SecurityExceptionService(db)
    exc = await svc.update_exception(exception_id, data)
    return APIResponse(data=exc, message="Exception updated")


@router.post("/{exception_id}/review", response_model=APIResponse[SecurityExceptionResponse])
async def review_exception(
    exception_id: str,
    data: SecurityExceptionReview,
    current_user: ComplianceUser,
    db: DBSession,
):
    logger.info(
        f"[exceptions:review] exception_id={exception_id[:8]} "
        f"action={data.action} by={current_user['user_id'][:8]}"
    )
    svc = SecurityExceptionService(db)
    exc = await svc.review_exception(exception_id, data, current_user["user_id"])
    return APIResponse(data=exc, message=f"Exception {data.action}d")


@router.post("/{exception_id}/revoke", response_model=APIResponse[SecurityExceptionResponse])
async def revoke_exception(
    exception_id: str,
    current_user: ComplianceUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Revoke an active exception before its expiry."""
    logger.info(
        f"[exceptions:revoke] exception_id={exception_id[:8]} "
        f"tenant={tenant_id[:8]} by={current_user['user_id'][:8]}"
    )
    svc = SecurityExceptionService(db)
    exc = await svc.revoke_exception(exception_id, tenant_id, current_user["user_id"])
    return APIResponse(data=exc, message="Exception revoked")
