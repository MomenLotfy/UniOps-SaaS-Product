from __future__ import annotations
"""Savings API — cost optimization recommendations with apply/dismiss actions."""
from fastapi import APIRouter, Query, Request
from typing import Optional
from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession
from app.schemas.cost import SavingsResponse, SavingActionResult
from app.schemas.common import APIResponse

router = APIRouter()

async def _check_rate_limit(request: Request, action: str) -> None:
    try:
        from app.core.redis_client import get_redis
        from fastapi import HTTPException, status as http_status
        redis  = await get_redis()
        uid    = getattr(request.state, "user_id", "anon")
        key    = f"rl:savings:{action}:{uid}"
        count  = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)
        if count > 5:
            raise HTTPException(
                status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit: max 5 requests/min for saving actions",
            )
    except Exception:
        pass  # Redis unavailable — skip, don't block


@router.get("", response_model=APIResponse[list[SavingsResponse]])
async def list_savings(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    status: Optional[str]   = Query(None),
    provider: Optional[str] = Query(None),
):
    from app.services.cost_service import CostService
    svc   = CostService(db)
    items = await svc.list_savings(tenant_id, status, provider)
    return APIResponse(data=items)


@router.post("/{saving_id}/apply", response_model=APIResponse[SavingActionResult])
async def apply_saving(
    saving_id: str,
    request: Request,
    current_user: AdminUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Apply a cost-saving recommendation (rightsizing, RI purchase, etc.)."""
    await _check_rate_limit(request, "apply")
    from app.services.cost_service import CostService
    from app.core.cache import cost_cache_invalidate
    svc    = CostService(db)
    result = await svc.apply_saving(
        saving_id  = saving_id,
        tenant_id  = tenant_id,
        applied_by = str(current_user.id),
    )
    await db.commit()
    # Bust cost cache so summary reflects the change
    await cost_cache_invalidate(tenant_id)
    return APIResponse(data=result, message=result.message)


@router.post("/{saving_id}/dismiss", response_model=APIResponse[SavingsResponse])
async def dismiss_saving(
    saving_id: str,
    request: Request,
    current_user: AdminUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Dismiss a saving recommendation — removes it from the active list."""
    await _check_rate_limit(request, "dismiss")
    from app.services.cost_service import CostService
    from app.core.cache import cost_cache_invalidate
    svc    = CostService(db)
    result = await svc.dismiss_saving(
        saving_id    = saving_id,
        tenant_id    = tenant_id,
        dismissed_by = str(current_user.id),
    )
    await db.commit()
    await cost_cache_invalidate(tenant_id)
    return APIResponse(data=result, message="Saving dismissed")


@router.get("/summary", response_model=APIResponse[dict])
async def get_savings_summary(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    """Total savings opportunity across all open/pending recommendations."""
    from app.services.cost_service import CostService
    svc    = CostService(db)
    result = await svc.get_total_savings_opportunity(tenant_id)
    return APIResponse(data=result)
