from __future__ import annotations
"""Security Policies API — Policy Engine with Audit/Enforce modes and violation tracking."""
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel as PydanticModel
from app.api.deps import (
    CurrentUser, SecurityReadUser, SecurityWriteUser, ComplianceUser,
    TenantID, DBSession,
)
from app.schemas.security_policy import (
    SecurityPolicyCreate, SecurityPolicyUpdate, SecurityPolicyResponse,
)
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.security_policy_service import SecurityPolicyService
from app.services.policy_evaluator import PolicyEvaluator
from app.utils.logger import logger

router = APIRouter()


class EnforcementToggle(PydanticModel):
    enforcement: str  # audit | enforce | advisory


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


@router.post("/seed-defaults", response_model=APIResponse)
async def seed_default_policies(
    current_user: SecurityWriteUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Seed the 5 built-in policy templates (idempotent)."""
    evaluator = PolicyEvaluator(db)
    created   = await evaluator.seed_builtin_policies(tenant_id, current_user["user_id"])
    return APIResponse(
        data={"created": len(created), "policies": created},
        message=f"{len(created)} built-in policies seeded" if created else "Built-in policies already exist",
    )


@router.get("/violations", response_model=APIResponse)
async def list_violations(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
    policy_id:   Optional[str] = None,
    entity_type: Optional[str] = None,
    status:      Optional[str] = None,
    enforcement: Optional[str] = None,
    limit:       int = Query(100, le=500),
    offset:      int = 0,
):
    """List policy violations across all scans."""
    evaluator = PolicyEvaluator(db)
    data = await evaluator.list_violations(
        tenant_id=tenant_id, policy_id=policy_id,
        entity_type=entity_type, status=status, enforcement=enforcement,
        limit=limit, offset=offset,
    )
    return APIResponse(data=data)


@router.get("/violations/summary", response_model=APIResponse)
async def violation_summary(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Aggregated violation counts by rule, enforcement mode, and status."""
    evaluator = PolicyEvaluator(db)
    data = await evaluator.get_violation_summary(tenant_id)
    return APIResponse(data=data)


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
    svc = SecurityPolicyService(db)
    policy = await svc.update_policy(policy_id, data, current_user["user_id"])
    return APIResponse(data=policy, message="Policy updated")


@router.patch("/{policy_id}/enforcement", response_model=APIResponse[SecurityPolicyResponse])
async def set_enforcement_mode(
    policy_id:    str,
    body:         EnforcementToggle,
    current_user: SecurityWriteUser,
    db: DBSession,
):
    """Toggle between audit / enforce / advisory modes."""
    if body.enforcement not in ("audit", "enforce", "advisory"):
        return APIResponse(data=None, message="enforcement must be audit | enforce | advisory", success=False)
    from app.schemas.security_policy import SecurityPolicyUpdate
    svc = SecurityPolicyService(db)
    policy = await svc.update_policy(
        policy_id, SecurityPolicyUpdate(enforcement=body.enforcement), current_user["user_id"]
    )
    return APIResponse(data=policy, message=f"Policy set to {body.enforcement} mode")


@router.delete("/{policy_id}", response_model=APIResponse)
async def delete_policy(
    policy_id: str,
    current_user: SecurityWriteUser,
    db: DBSession,
):
    svc = SecurityPolicyService(db)
    await svc.delete_policy(policy_id)
    return APIResponse(data=None, message="Policy deleted")
