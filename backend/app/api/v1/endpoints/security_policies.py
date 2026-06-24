from __future__ import annotations
"""Security Policies API — manage DevSecOps security policies with RBAC enforcement."""
from typing import Optional
from fastapi import APIRouter, Query
from app.api.deps import (
    CurrentUser, SecurityReadUser, SecurityWriteUser, ComplianceUser,
    TenantID, DBSession,
)
from app.schemas.security_policy import (
    SecurityPolicyCreate, SecurityPolicyUpdate, SecurityPolicyResponse,
)
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.security_policy_service import SecurityPolicyService
from app.utils.logger import logger

router = APIRouter()


@router.get("", response_model=APIResponse)
async def list_policies(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    enforcement: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
):
    logger.info(f"[policies:list] tenant={tenant_id[:8]} category={category} status={status}")
    svc = SecurityPolicyService(db)
    result = await svc.list_policies(
        tenant_id, page, page_size,
        category=category, status=status,
        severity=severity, enforcement=enforcement, framework=framework,
    )
    return APIResponse(data=result)


@router.post("", response_model=APIResponse[SecurityPolicyResponse])
async def create_policy(
    data: SecurityPolicyCreate,
    current_user: SecurityWriteUser,
    tenant_id: TenantID,
    db: DBSession,
):
    logger.info(f"[policies:create] tenant={tenant_id[:8]} by={current_user['user_id'][:8]}")
    svc = SecurityPolicyService(db)
    policy = await svc.create_policy(tenant_id, data, current_user["user_id"])
    return APIResponse(data=policy, message="Policy created")


@router.get("/stats", response_model=APIResponse)
async def get_policy_stats(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    svc = SecurityPolicyService(db)
    stats = await svc.get_stats(tenant_id)
    return APIResponse(data=stats)


@router.get("/{policy_id}", response_model=APIResponse[SecurityPolicyResponse])
async def get_policy(
    policy_id: str,
    current_user: SecurityReadUser,
    db: DBSession,
):
    svc = SecurityPolicyService(db)
    policy = await svc.get_policy(policy_id)
    return APIResponse(data=policy)


@router.patch("/{policy_id}", response_model=APIResponse[SecurityPolicyResponse])
async def update_policy(
    policy_id: str,
    data: SecurityPolicyUpdate,
    current_user: SecurityWriteUser,
    db: DBSession,
):
    logger.info(f"[policies:update] policy_id={policy_id[:8]} by={current_user['user_id'][:8]}")
    svc = SecurityPolicyService(db)
    policy = await svc.update_policy(policy_id, data, current_user["user_id"])
    return APIResponse(data=policy, message="Policy updated")


@router.delete("/{policy_id}", response_model=APIResponse)
async def delete_policy(
    policy_id: str,
    current_user: SecurityWriteUser,
    db: DBSession,
):
    logger.info(f"[policies:delete] policy_id={policy_id[:8]} by={current_user['user_id'][:8]}")
    svc = SecurityPolicyService(db)
    await svc.delete_policy(policy_id)
    return APIResponse(data=None, message="Policy deleted")
