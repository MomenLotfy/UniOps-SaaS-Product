from __future__ import annotations
"""ML API — predictions, recommendations, patterns, and correlations."""
from typing import Optional
from fastapi import APIRouter, Query
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.ml import MLInsightResponse, ModelStatus
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.ml_service import MLService

router = APIRouter()


@router.get("/predictions", response_model=APIResponse[PaginatedResponse])
async def list_predictions(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
):
    svc = MLService(db)
    result = await svc.list_predictions(tenant_id, page, page_size)
    return APIResponse(data=result)


@router.get("/recommendations")
async def list_recommendations(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    category: Optional[str] = Query(None),
):
    svc = MLService(db)
    items = await svc.list_recommendations(tenant_id, category)
    return APIResponse(data=items)


@router.get("/patterns")
async def list_patterns(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = MLService(db)
    patterns = await svc.list_patterns(tenant_id)
    return APIResponse(data=patterns)


@router.get("/correlations")
async def list_correlations(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = MLService(db)
    correlations = await svc.list_correlations(tenant_id)
    return APIResponse(data=correlations)


@router.post("/predict/cost", response_model=APIResponse[MLInsightResponse])
async def predict_cost(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    months_ahead: int = Query(3, ge=1, le=12),
):
    svc = MLService(db)
    result = await svc.predict_cost(tenant_id, months_ahead)
    return APIResponse(data=result)


@router.post("/detect/anomalies", response_model=APIResponse[MLInsightResponse])
async def detect_anomalies(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = MLService(db)
    result = await svc.detect_anomalies(tenant_id)
    return APIResponse(data=result)


@router.get("/models/status")
async def get_model_statuses(current_user: CurrentUser, db: DBSession):
    svc = MLService(db)
    statuses = await svc.get_model_statuses()
    return APIResponse(data=statuses)


@router.post("/models/retrain")
async def trigger_retrain(current_user: CurrentUser, db: DBSession):
    from app.tasks.train_ml_models import retrain_all
    task = retrain_all.delay()
    return APIResponse(data={"task_id": task.id}, message="Model retraining triggered")


@router.get("/stats")
async def get_ml_stats(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    """Quick stats for the Command Center summary card."""
    from sqlalchemy import select, func
    from app.models.ml_pattern import MLPattern
    from app.models.ml_recommendation import MLRecommendation
    from app.models.ml_prediction import MLPrediction

    patterns_count = (await db.execute(
        select(func.count(MLPattern.id)).where(MLPattern.tenant_id == tenant_id)
    )).scalar() or 0

    recs_count = (await db.execute(
        select(func.count(MLRecommendation.id)).where(MLRecommendation.tenant_id == tenant_id)
    )).scalar() or 0

    latest_pred = (await db.execute(
        select(MLPrediction).where(MLPrediction.tenant_id == tenant_id)
        .order_by(MLPrediction.predicted_at.desc()).limit(1)
    )).scalar_one_or_none()

    accuracy = latest_pred.confidence if latest_pred else None

    return APIResponse(data={
        "patterns_found": patterns_count,
        "recommendations": recs_count,
        "accuracy": accuracy,
    })


# ── Alert Rules ───────────────────────────────────────────────────────────────

from pydantic import BaseModel as PydanticBaseModel, Field


class AlertRuleCreate(PydanticBaseModel):
    """
    Request body for POST /ml/alert-rules.

    Mapped to the existing Alert model using:
      title     ← name
      category  ← "ml_pattern"
      source    ← "ml_listener"
      metadata_ ← all extra fields (condition, schedule, etc.)
      is_read   ← False  (alert rule — not a fired alert notification)
      status    ← "active"

    This avoids any DB schema change: we store rule metadata in the
    existing JSON metadata_ column, which is already indexed as JSONB.
    """
    name:         str           = Field(..., min_length=1, max_length=499,
                                        description="Human-readable rule name")
    condition:    str           = Field(..., min_length=1,
                                        description="Trigger condition (e.g. 'cpu_usage > 80')")
    pattern_id:   Optional[str] = Field(None,
                                        description="ML pattern ID that triggered this rule")
    schedule:     str           = Field("daily",
                                        description="Evaluation cadence: daily | weekly | realtime")
    scale_target: Optional[int] = Field(None, ge=1, le=50,
                                        description="Target replica count if scaling action needed")
    notify_slack: bool          = Field(False,
                                        description="Send Slack notification when rule fires")


@router.post("/alert-rules", status_code=201)
async def create_alert_rule(
    payload: AlertRuleCreate,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """
    Persist an ML-generated alert rule to the database.

    BEFORE this endpoint: the frontend called setToast() locally and the rule
    vanished on page refresh.  The "Create Alert Rule" button in ML Insights
    Patterns tab was entirely client-side theater.

    AFTER: rule persists in the alerts table, downstream ML and notification
    systems receive ALERT_FIRED via Redis pub/sub, and the rule survives
    service restarts.

    WHY FAKE ALERTS ARE DANGEROUS
    ──────────────────────────────
    A fake alert gives the operator false confidence that a scaling or
    notification rule is active.  When the real condition fires (e.g. CPU
    spike every Friday 1:30 PM UTC as predicted by PatternDiscoverer), no
    automation triggers, no Slack message fires, and the on-call engineer
    discovers the problem manually — minutes or hours later.

    TENANT ISOLATION
    ────────────────
    tenant_id comes from the JWT via TenantID dependency — never from the
    request body — so cross-tenant rule creation is impossible.

    EVENT PUBLISHING
    ────────────────
    Publishing is wrapped in try/except so a Redis outage never causes the
    endpoint to return 500.  The rule is already persisted in PostgreSQL
    before the publish is attempted; Redis failure only means downstream
    consumers do not receive the immediate notification (they will pick it
    up on the next scheduled ML correlation run).
    """
    from app.models.alert import Alert
    from app.utils.logger import logger

    # ── 1. Persist rule using existing Alert model ────────────────────────────
    rule = Alert(
        tenant_id = tenant_id,
        title     = payload.name,
        message   = payload.condition,
        severity  = "info",
        category  = "ml_pattern",
        source    = "ml_listener",
        status    = "active",
        is_read   = False,
        resource  = payload.pattern_id,
        metadata_ = {
            "condition":    payload.condition,
            "schedule":     payload.schedule,
            "scale_target": payload.scale_target,
            "notify_slack": payload.notify_slack,
            "pattern_id":   payload.pattern_id,
            "created_by":   str(current_user.id),
            "rule_type":    "ml_pattern",
        },
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    logger.info(
        f"[AlertRule] Created — id={rule.id} name={payload.name!r} "
        f"tenant={tenant_id[:8]} pattern={payload.pattern_id}"
    )

    # ── 2. Publish ALERT_FIRED (non-blocking — Redis failure is safe) ─────────
    try:
        from app.events.bus import event_bus
        from app.events.events import EventType

        await event_bus.publish(
            EventType.ALERT_FIRED,
            payload={
                "rule_id":      str(rule.id),
                "name":         rule.title,
                "condition":    payload.condition,
                "schedule":     payload.schedule,
                "notify_slack": payload.notify_slack,
                "pattern_id":   payload.pattern_id,
            },
            tenant_id=tenant_id,
        )
        logger.info(
            f"[EventBus] ALERT_FIRED published — "
            f"rule_id={rule.id} tenant={tenant_id[:8]}"
        )
    except Exception as exc:
        # Non-fatal: rule is already in PostgreSQL.
        # Redis outage does not roll back the alert rule.
        logger.warning(
            f"[EventBus] ALERT_FIRED publish failed (non-fatal) — "
            f"rule_id={rule.id}: {exc!r}"
        )

    return APIResponse(
        data    = {"id": str(rule.id), "name": rule.title, "status": rule.status},
        message = f"Alert rule '{payload.name}' created successfully",
    )
