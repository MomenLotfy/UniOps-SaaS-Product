"""
Catalog API — Self-Service Catalog CRUD + Deployment Engine integration (Epic 7).

Endpoints:
  GET    /catalog/services              — list services for tenant
  POST   /catalog/services              — create service (triggers full pipeline)
  GET    /catalog/services/{id}         — get single service
  PATCH  /catalog/services/{id}/status  — manual status update (admin)
  DELETE /catalog/services/{id}         — soft delete (mark Stopped)
  GET    /catalog/services/{id}/logs    — deployment logs for a service
  GET    /catalog/stats                 — aggregate stats
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel as PydanticModel, Field, field_validator
from sqlalchemy import select, func

from app.api.deps import CurrentUser, TenantID, DBSession
from app.core.deployment_engine.service import DeploymentEngine, ServiceCreatePayload
from app.models.deployment_log import DeploymentLog
from app.models.service import CatalogService

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Request / Response schemas ─────────────────────────────────────────────────

class ServiceCreateRequest(PydanticModel):
    name:        str       = Field(..., min_length=2, max_length=100)
    type:        str       = Field(default="Microservice")
    tech_stack:  str       = Field(default="Other")
    description: Optional[str] = None
    git_repo:    Optional[str] = None
    cluster:     str       = Field(default="")
    namespace:   str       = Field(default="default")
    replicas:    int       = Field(default=1, ge=1, le=50)
    owner:       Optional[str] = None
    tags:        list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_slug(cls, v: str) -> str:
        import re
        v = v.lower().strip()
        v = re.sub(r"[^a-z0-9-]", "-", v)
        v = re.sub(r"-+", "-", v).strip("-")
        return v


class ServiceStatusUpdate(PydanticModel):
    status: str


def _svc_dict(s: CatalogService) -> dict:
    return {
        "id":              s.id,
        "name":            s.name,
        "type":            s.type,
        "tech_stack":      s.tech_stack,
        "status":          s.status,
        "description":     s.description,
        "owner":           s.owner,
        "repo_url":        s.repo_url,
        "git_provider":    s.git_provider,
        "cluster":         s.cluster,
        "namespace":       s.namespace,
        "replicas":        s.replicas,
        "gitops_app_name": s.gitops_app_name,
        "helm_chart_path": s.helm_chart_path,
        "last_deployment": s.last_deployment,
        "tags":            s.tags or [],
        "meta":            s.meta or {},
        "created_at":      s.created_at.isoformat(),
        "updated_at":      s.updated_at.isoformat(),
    }


def _log_dict(l: DeploymentLog) -> dict:
    return {
        "id":           l.id,
        "service_id":   l.service_id,
        "service_name": l.service_name,
        "step":         l.step,
        "status":       l.status,
        "message":      l.message,
        "error":        l.error,
        "duration_ms":  l.duration_ms,
        "meta":         l.meta or {},
        "created_at":   l.created_at.isoformat(),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/services")
async def list_services(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    status:       Optional[str] = Query(None),
    type:         Optional[str] = Query(None, alias="type"),
    search:       Optional[str] = Query(None),
    page:         int           = Query(1, ge=1),
    page_size:    int           = Query(50, ge=1, le=200),
):
    q = select(CatalogService).where(CatalogService.tenant_id == tenant_id)

    if status:
        q = q.where(CatalogService.status == status)
    if type:
        q = q.where(CatalogService.type == type)
    if search:
        q = q.where(CatalogService.name.ilike(f"%{search}%"))

    q = q.order_by(CatalogService.created_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(q)
    services = result.scalars().all()

    # Total count
    count_q = select(func.count(CatalogService.id)).where(CatalogService.tenant_id == tenant_id)
    total   = (await db.execute(count_q)).scalar_one()

    return {
        "success": True,
        "data":    [_svc_dict(s) for s in services],
        "total":   total,
        "page":    page,
        "page_size": page_size,
    }


@router.post("/services", status_code=202)
async def create_service(
    body:         ServiceCreateRequest,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    # Check for name collision
    existing = await db.execute(
        select(CatalogService).where(
            CatalogService.tenant_id == tenant_id,
            CatalogService.name == body.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Service '{body.name}' already exists")

    engine  = DeploymentEngine(db, tenant_id, user_id=current_user.get("user_id", ""))
    payload = ServiceCreatePayload(body.model_dump())
    svc     = await engine.create_service(payload)

    logger.info(f"[catalog] Service creation initiated: {svc.name} ({svc.id}) for tenant {tenant_id}")

    return {
        "success": True,
        "message": f"Service '{svc.name}' creation initiated. Deployment pipeline running.",
        "data":    _svc_dict(svc),
    }


@router.get("/services/{service_id}")
async def get_service(
    service_id:   str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    result = await db.execute(
        select(CatalogService).where(
            CatalogService.id == service_id,
            CatalogService.tenant_id == tenant_id,
        )
    )
    svc = result.scalar_one_or_none()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"success": True, "data": _svc_dict(svc)}


@router.patch("/services/{service_id}/status")
async def update_service_status(
    service_id:   str,
    body:         ServiceStatusUpdate,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    roles = current_user.get("roles", [])
    if not any(r in roles for r in ("admin", "super_admin", "devops")):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(
        select(CatalogService).where(
            CatalogService.id == service_id,
            CatalogService.tenant_id == tenant_id,
        )
    )
    svc = result.scalar_one_or_none()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    from sqlalchemy import update
    await db.execute(
        update(CatalogService)
        .where(CatalogService.id == service_id)
        .values(status=body.status)
    )
    await db.commit()
    return {"success": True, "message": f"Status updated to {body.status}"}


@router.delete("/services/{service_id}", status_code=204)
async def delete_service(
    service_id:   str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    from sqlalchemy import update
    result = await db.execute(
        update(CatalogService)
        .where(CatalogService.id == service_id, CatalogService.tenant_id == tenant_id)
        .values(status="Stopped")
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Service not found")
    await db.commit()


@router.get("/services/{service_id}/logs")
async def get_deployment_logs(
    service_id:   str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    limit:        int = Query(100, ge=1, le=500),
):
    result = await db.execute(
        select(DeploymentLog)
        .where(
            DeploymentLog.service_id == service_id,
            DeploymentLog.tenant_id  == tenant_id,
        )
        .order_by(DeploymentLog.created_at.asc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return {"success": True, "data": [_log_dict(l) for l in logs]}


@router.get("/stats")
async def get_catalog_stats(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    result = await db.execute(
        select(CatalogService.status, func.count(CatalogService.id))
        .where(CatalogService.tenant_id == tenant_id)
        .group_by(CatalogService.status)
    )
    rows   = result.all()
    counts = {row[0]: row[1] for row in rows}

    total   = sum(counts.values())
    running = counts.get("Running",   0)
    failed  = counts.get("Failed",    0)
    pending = counts.get("Deploying", 0) + counts.get("Creating", 0) + counts.get("Building", 0)

    return {
        "success": True,
        "data": {
            "total":     total,
            "running":   running,
            "failed":    failed,
            "deploying": pending,
            "stopped":   counts.get("Stopped", 0),
            "by_status": counts,
        },
    }
