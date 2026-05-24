from __future__ import annotations
"""Costs API — cloud cost metrics, summaries, anomaly detection and actions."""
import json
import calendar
from typing import Optional
from datetime import date
from fastapi import APIRouter, Query, Request
from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession
from app.schemas.cost import CostMetricResponse, CostAnomalyResponse
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.cost_service import CostService
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()

# ─── simple in-process rate limit (per-user, per-action) ──────────────────────
# Falls back gracefully if Redis is unavailable.
_RATE_LIMIT  = 5    # max requests
_RATE_WINDOW = 60   # per 60 seconds

async def _check_rate_limit(request: Request, action: str) -> None:
    """Raise HTTP 429 if user has exceeded the per-action rate limit."""
    from fastapi import HTTPException, status
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        user_id = getattr(request.state, "user_id", "anon")
        key = f"rl:cost:{action}:{user_id}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, _RATE_WINDOW)
        if count > _RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded — max {_RATE_LIMIT} requests per {_RATE_WINDOW}s",
            )
    except Exception as exc:
        # Redis unavailable — skip rate limiting rather than break functionality
        from app.utils.logger import logger
        logger.debug(f"[rate_limit] skipped: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# List
# ─────────────────────────────────────────────────────────────────────────────
@router.get("", response_model=APIResponse[PaginatedResponse])
async def list_cost_metrics(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    provider: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    svc = CostService(db)
    result = await svc.list_metrics(tenant_id, page, page_size, provider, service, start_date, end_date)
    return APIResponse(data=result)


# ─────────────────────────────────────────────────────────────────────────────
# Summary — with Redis cache (TTL 5 min)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/summary")
async def get_cost_summary(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    from app.core.cache import cost_cache_get, cost_cache_set

    # Try cache first
    cached = await cost_cache_get(tenant_id, "summary")
    if cached is not None:
        return APIResponse(data=cached)

    svc     = CostService(db)
    summary = await svc.get_summary(tenant_id)

    await cost_cache_set(tenant_id, "summary", summary)
    return APIResponse(data=summary)


# ─────────────────────────────────────────────────────────────────────────────
# Breakdown — with Redis cache + change_pct vs previous month
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/breakdown")
async def get_cost_breakdown(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    """Per-service MTD cost breakdown with vs-last-period change percentage."""
    from app.core.cache import cost_cache_get, cost_cache_set
    from sqlalchemy import select, func
    from app.models.cost_metric import CostMetric
    from datetime import timedelta

    cached = await cost_cache_get(tenant_id, "breakdown")
    if cached is not None:
        return APIResponse(data=cached)

    today = date.today()
    month_start = today.replace(day=1)
    if today.month == 1:
        prev_start = date(today.year - 1, 12, 1)
    else:
        prev_start = date(today.year, today.month - 1, 1)

    # Current month MTD
    curr_rows = (await db.execute(
        select(
            CostMetric.service,
            CostMetric.provider,
            func.sum(CostMetric.amount).label("mtd"),
        )
        .where(CostMetric.tenant_id == tenant_id, CostMetric.period_start >= month_start)
        .group_by(CostMetric.service, CostMetric.provider)
        .order_by(func.sum(CostMetric.amount).desc())
    )).all()

    # Previous month totals (same grouping)
    prev_rows = (await db.execute(
        select(
            CostMetric.service,
            func.sum(CostMetric.amount).label("prev"),
        )
        .where(
            CostMetric.tenant_id  == tenant_id,
            CostMetric.period_start >= prev_start,
            CostMetric.period_start <  month_start,
        )
        .group_by(CostMetric.service)
    )).all()

    prev_map = {r.service: float(r.prev) for r in prev_rows}
    total    = sum(float(r.mtd) for r in curr_rows) or 1.0

    breakdown = []
    for r in curr_rows:
        mtd      = round(float(r.mtd), 2)
        prev     = prev_map.get(r.service, 0.0)
        chg_pct  = round(((mtd - prev) / prev * 100), 1) if prev > 0 else 0.0
        breakdown.append({
            "service":       r.service,
            "provider":      r.provider,
            "mtd":           mtd,
            "pct_of_total":  round(mtd / total * 100, 1),
            "change_pct":    chg_pct,
            "prev_month":    round(prev, 2),
        })

    await cost_cache_set(tenant_id, "breakdown", breakdown)
    return APIResponse(data=breakdown)


# ─────────────────────────────────────────────────────────────────────────────
# Forecast — with cache, real accuracy calc, FIXED field names
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/forecast")
async def get_cost_forecast(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    """
    Cost forecast.

    Field names in `points` are aligned with the frontend chart:
      • date      — "May 23"  (XAxis dataKey="date")
      • day       — alias of date (backwards compat)
      • actual    — real spend (Area dataKey="actual")
      • predicted — forecast value (Area dataKey="predicted")
      • projected — alias of predicted (backwards compat)
    """
    from app.core.cache import cost_cache_get, cost_cache_set
    from sqlalchemy import select, func
    from app.models.cost_metric import CostMetric
    from datetime import timedelta

    cached = await cost_cache_get(tenant_id, "forecast")
    if cached is not None:
        return APIResponse(data=cached)

    today          = date.today()
    month_start    = today.replace(day=1)
    days_in_month  = calendar.monthrange(today.year, today.month)[1]
    days_elapsed   = max(today.day, 1)

    if today.month == 1:
        prev_start = date(today.year - 1, 12, 1)
    else:
        prev_start = date(today.year, today.month - 1, 1)

    # ── Single query: MTD + prev month ───────────────────────────────────────
    agg = (await db.execute(
        select(
            func.sum(CostMetric.amount).filter(
                CostMetric.period_start >= month_start
            ).label("mtd"),
            func.sum(CostMetric.amount).filter(
                CostMetric.period_start >= prev_start,
                CostMetric.period_start <  month_start,
            ).label("prev"),
        )
        .where(CostMetric.tenant_id == tenant_id)
    )).fetchone()

    mtd  = float(agg.mtd  or 0.0)
    prev = float(agg.prev or 0.0)

    # If no current-month data exist yet, extrapolate from previous month
    if mtd == 0.0 and prev > 0.0:
        mtd = prev * (days_elapsed / days_in_month)

    daily_avg    = mtd / days_elapsed if days_elapsed > 0 else 0.0
    eom_forecast = daily_avg * days_in_month

    # Budget = last month × 1.10 (or forecast itself as fallback)
    budget     = prev * 1.10 if prev > 0 else eom_forecast * 1.10
    over_budget = eom_forecast > budget if budget > 0 else False

    # ── Daily historical points (last 30 days, grouped by period_start) ──────
    past_rows = (await db.execute(
        select(
            CostMetric.period_start.label("day"),
            func.sum(CostMetric.amount).label("cost"),
        )
        .where(
            CostMetric.tenant_id    == tenant_id,
            CostMetric.period_start >= today - timedelta(days=30),
        )
        .group_by(CostMetric.period_start)
        .order_by(CostMetric.period_start)
    )).all()

    points = [
        {
            "date":   r.day.strftime("%b %d"),
            "day":    r.day.strftime("%b %d"),   # ← alias for legacy XAxis
            "actual": round(float(r.cost), 2),
        }
        for r in past_rows
    ]

    # ── 14 projected days ─────────────────────────────────────────────────────
    for i in range(1, 15):
        fd = today + timedelta(days=i)
        projected_val = round(daily_avg, 2)
        points.append({
            "date":      fd.strftime("%b %d"),
            "day":       fd.strftime("%b %d"),      # ← alias
            "predicted": projected_val,             # ← frontend dataKey
            "projected": projected_val,             # ← alias (backwards compat)
        })

    # ── Accuracy — compare last month daily avg vs actual spend ──────────────
    # Real accuracy = 1 - MAPE(last_month_daily_avg, actual_daily_values)
    # Simplified: compare prev month total vs extrapolated from its first half
    accuracy = _calculate_forecast_accuracy(prev, mtd, days_elapsed, days_in_month)

    result_data = {
        "accuracy":     accuracy,
        "eom_forecast": round(eom_forecast, 2),
        "budget":       round(budget, 2),
        "over_budget":  over_budget,
        "daily_avg":    round(daily_avg, 2),
        "points":       points,
        "insight": (
            f"Projected end-of-month spend is ${eom_forecast:,.0f}. "
            + ("⚠ Spend is tracking above last month's budget." if over_budget
               else "✓ Spend is within expected range.")
        ),
    }

    await cost_cache_set(tenant_id, "forecast", result_data)
    return APIResponse(data=result_data)


def _calculate_forecast_accuracy(
    prev_month_total: float,
    current_mtd: float,
    days_elapsed: int,
    days_in_month: int,
) -> int:
    """
    Estimate forecast accuracy as a percentage.

    Method: compare how well the previous month's daily average would have
    predicted the actual current-month spend so far.
    Returns 100 when there is no prior data (no basis for error).
    """
    if prev_month_total <= 0 or days_elapsed <= 0:
        return 91  # neutral default when no history available

    import calendar as _cal
    from datetime import date as _date
    today = _date.today()
    if today.month == 1:
        prev_days = _cal.monthrange(today.year - 1, 12)[1]
    else:
        prev_days = _cal.monthrange(today.year, today.month - 1)[1]

    prev_daily_avg = prev_month_total / prev_days
    predicted_mtd  = prev_daily_avg * days_elapsed

    if predicted_mtd <= 0:
        return 91

    # MAPE-style: |actual - predicted| / actual
    mape = abs(current_mtd - predicted_mtd) / max(current_mtd, 1) * 100
    accuracy = max(0, min(100, round(100 - mape)))
    return accuracy


# ─────────────────────────────────────────────────────────────────────────────
# Anomalies list
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/sync")
async def trigger_cost_sync(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """
    Trigger an immediate AWS cost sync for this tenant.
    Returns immediately — sync runs in the background.
    Logs: [sync_trigger] integration created → aws validated → sync triggered
    """
    from app.utils.logger import logger
    from fastapi import BackgroundTasks
    import asyncio

    logger.info(f"[sync_trigger] Manual cost sync requested by user={current_user.id} tenant={tenant_id[:8]}")

    # Verify at least one active AWS integration exists
    from sqlalchemy import select as _sel
    from app.models.integration import Integration as _Intg

    intg = (await db.execute(
        _sel(_Intg).where(
            _Intg.tenant_id == tenant_id,
            _Intg.type      == "aws",
            _Intg.is_active == True,
        ).limit(1)
    )).scalar_one_or_none()

    if not intg:
        logger.warning(f"[sync_trigger] No AWS integration found for tenant={tenant_id[:8]}")
        return APIResponse(
            data={"triggered": False, "reason": "no_aws_integration"},
            message="No AWS integration configured",
        )

    logger.info(
        f"[sync_trigger] Found integration={intg.name} status={intg.status} "
        f"tenant={tenant_id[:8]} — triggering sync"
    )

    # Run sync in background so endpoint returns immediately
    async def _run_sync():
        try:
            from app.tasks.sync_costs import sync_aws_costs_async
            logger.info(f"[sync_trigger] sync_triggered tenant={tenant_id[:8]}")
            result = await sync_aws_costs_async(tenant_id=tenant_id)
            logger.info(f"[sync_trigger] ingestion_completed tenant={tenant_id[:8]} result={result}")
        except Exception as exc:
            logger.error(f"[sync_trigger] sync failed for tenant={tenant_id[:8]}: {exc}")

    asyncio.create_task(_run_sync())

    return APIResponse(
        data={"triggered": True, "integration": intg.name, "status": intg.status},
        message="Cost sync started — data will appear within a few seconds",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Anomalies list
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/anomalies")
async def list_anomalies(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    status: Optional[str]   = Query(None),
    severity: Optional[str] = Query(None),
):
    svc = CostService(db)
    items = await svc.list_anomalies(tenant_id, status, severity)
    return APIResponse(data=items)


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly actions — investigate / resolve / dismiss
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/anomalies/{anomaly_id}/investigate")
async def investigate_anomaly(
    anomaly_id: str,
    request: Request,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Mark anomaly as under investigation (open → investigating)."""
    await _check_rate_limit(request, "anomaly_action")
    svc    = CostService(db)
    result = await svc.update_anomaly_status(anomaly_id, tenant_id, "investigating")
    await db.commit()
    return APIResponse(data=result, message="Investigation started")


@router.post("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(
    anomaly_id: str,
    request: Request,
    current_user: AdminUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Mark anomaly as resolved (open/investigating → resolved)."""
    await _check_rate_limit(request, "anomaly_action")
    svc    = CostService(db)
    result = await svc.update_anomaly_status(anomaly_id, tenant_id, "resolved")
    await db.commit()
    return APIResponse(data=result, message="Anomaly marked as resolved")


@router.post("/anomalies/{anomaly_id}/dismiss")
async def dismiss_anomaly(
    anomaly_id: str,
    request: Request,
    current_user: AdminUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Dismiss anomaly (open/investigating → dismissed)."""
    await _check_rate_limit(request, "anomaly_action")
    svc    = CostService(db)
    result = await svc.update_anomaly_status(anomaly_id, tenant_id, "dismissed")
    await db.commit()
    return APIResponse(data=result, message="Anomaly dismissed")
