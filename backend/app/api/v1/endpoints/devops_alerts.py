from __future__ import annotations
"""DevOps Alerts API — Alert center for DevOps Center (Epic 4)."""
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.models.devops_alert import DevOpsAlert

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    name:       str
    severity:   str = "warning"
    type:       str
    resource:   Optional[str] = None
    namespace:  Optional[str] = None
    cluster_id: Optional[str] = None
    message:    str
    labels:     dict = {}
    annotations:dict = {}


class AlertAction(BaseModel):
    reason:     Optional[str] = None
    mute_hours: Optional[int] = None    # used for mute action


def _to_dict(a: DevOpsAlert) -> dict:
    return {
        "id":          a.id,
        "name":        a.name,
        "severity":    a.severity,
        "type":        a.type,
        "resource":    a.resource,
        "namespace":   a.namespace,
        "cluster_id":  a.cluster_id,
        "message":     a.message,
        "status":      a.status,
        "labels":      a.labels,
        "annotations": a.annotations,
        "muted_until": a.muted_until.isoformat() if a.muted_until else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        "fired_at":    a.fired_at.isoformat()    if a.fired_at    else None,
        "created_at":  a.created_at.isoformat(),
    }


# ── List + create ─────────────────────────────────────────────────────────────

@router.get("")
async def list_alerts(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    status:    Optional[str] = Query(None),
    severity:  Optional[str] = Query(None),
    namespace: Optional[str] = Query(None),
    cluster_id:Optional[str] = Query(None),
    page:      int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    q = select(DevOpsAlert).where(DevOpsAlert.tenant_id == tenant_id)
    if status:     q = q.where(DevOpsAlert.status    == status)
    if severity:   q = q.where(DevOpsAlert.severity  == severity)
    if namespace:  q = q.where(DevOpsAlert.namespace  == namespace)
    if cluster_id: q = q.where(DevOpsAlert.cluster_id == cluster_id)
    q = q.order_by(DevOpsAlert.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
    result = await db.execute(q)
    alerts = result.scalars().all()
    return APIResponse(data=[_to_dict(a) for a in alerts])


@router.post("", status_code=201)
async def create_alert(
    body: AlertCreate,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    alert = DevOpsAlert(
        tenant_id=tenant_id,
        name=body.name,
        severity=body.severity,
        type=body.type,
        resource=body.resource,
        namespace=body.namespace,
        cluster_id=body.cluster_id,
        message=body.message,
        labels=body.labels,
        annotations=body.annotations,
        fired_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return APIResponse(data=_to_dict(alert), message="Alert created")


# ── Alert actions ─────────────────────────────────────────────────────────────

@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str, body: AlertAction,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    result = await db.execute(
        select(DevOpsAlert).where(DevOpsAlert.id == alert_id, DevOpsAlert.tenant_id == tenant_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        return APIResponse(success=False, message="Alert not found")
    alert.status = "acknowledged"
    if body.reason:
        alert.annotations = {**alert.annotations, "ack_reason": body.reason}
    await db.commit()
    return APIResponse(data=_to_dict(alert), message="Alert acknowledged")


@router.post("/{alert_id}/mute")
async def mute_alert(
    alert_id: str, body: AlertAction,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    result = await db.execute(
        select(DevOpsAlert).where(DevOpsAlert.id == alert_id, DevOpsAlert.tenant_id == tenant_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        return APIResponse(success=False, message="Alert not found")
    hours = body.mute_hours or 4
    alert.status = "muted"
    alert.muted_until = datetime.now(timezone.utc) + timedelta(hours=hours)
    await db.commit()
    return APIResponse(data=_to_dict(alert), message=f"Alert muted for {hours}h")


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str, body: AlertAction,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    result = await db.execute(
        select(DevOpsAlert).where(DevOpsAlert.id == alert_id, DevOpsAlert.tenant_id == tenant_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        return APIResponse(success=False, message="Alert not found")
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return APIResponse(data=_to_dict(alert), message="Alert resolved")


@router.post("/{alert_id}/escalate")
async def escalate_alert(
    alert_id: str, body: AlertAction,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    result = await db.execute(
        select(DevOpsAlert).where(DevOpsAlert.id == alert_id, DevOpsAlert.tenant_id == tenant_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        return APIResponse(success=False, message="Alert not found")
    alert.severity = "critical"
    alert.annotations = {**alert.annotations, "escalated": True, "escalated_reason": body.reason or "Manual escalation"}
    await db.commit()
    return APIResponse(data=_to_dict(alert), message="Alert escalated to critical")


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    result = await db.execute(
        select(DevOpsAlert).where(DevOpsAlert.id == alert_id, DevOpsAlert.tenant_id == tenant_id)
    )
    alert = result.scalar_one_or_none()
    if alert:
        await db.delete(alert)
        await db.commit()


@router.get("/stats")
async def get_alert_stats(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    all_q = await db.execute(select(DevOpsAlert).where(DevOpsAlert.tenant_id == tenant_id))
    alerts = all_q.scalars().all()
    by_status   = {}
    by_severity = {}
    for a in alerts:
        by_status[a.status]     = by_status.get(a.status, 0) + 1
        by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
    return APIResponse(data={
        "total":      len(alerts),
        "firing":     by_status.get("firing", 0),
        "acknowledged":by_status.get("acknowledged", 0),
        "muted":      by_status.get("muted", 0),
        "resolved":   by_status.get("resolved", 0),
        "critical":   by_severity.get("critical", 0),
        "warning":    by_severity.get("warning", 0),
        "info":       by_severity.get("info", 0),
    })
