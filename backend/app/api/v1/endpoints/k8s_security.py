from __future__ import annotations
"""
Kubernetes Security API
=======================
GET  /k8s/clusters                        — list clusters with risk scores
GET  /k8s/clusters/{cluster_id}/scan-history
POST /k8s/clusters/{cluster_id}/scan      — trigger scan
GET  /k8s/findings                        — list findings (filterable)
GET  /k8s/findings/stats                  — severity/category summary
PATCH /k8s/findings/{finding_id}/suppress
PATCH /k8s/findings/{finding_id}/resolve
GET  /k8s/scans/{scan_id}                 — single scan details
"""
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, status as http_status

from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.k8s_security_service import K8sSecurityService
from app.utils.logger import logger

router = APIRouter()


# ── Clusters ──────────────────────────────────────────────────────────────────

@router.get("/clusters")
async def list_k8s_clusters(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    svc = K8sSecurityService(db)
    clusters = await svc.list_clusters(tenant_id)
    return APIResponse(data=clusters)


@router.get("/clusters/{cluster_id}/scan-history")
async def get_scan_history(
    cluster_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    limit: int = Query(10, ge=1, le=50),
):
    svc = K8sSecurityService(db)
    history = await svc.get_scan_history(tenant_id, cluster_id, limit=limit)
    return APIResponse(data=history)


@router.post("/clusters/{cluster_id}/scan")
async def trigger_cluster_scan(
    cluster_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    svc = K8sSecurityService(db)
    try:
        scan = await svc.trigger_scan(tenant_id, cluster_id)
        logger.info(f"[k8s_security] Scan {scan.id} triggered for cluster {cluster_id} by {current_user.id}")
        return APIResponse(data=scan.to_dict(), message="Scan started")
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))


# ── Findings ──────────────────────────────────────────────────────────────────

@router.get("/findings/stats")
async def get_findings_stats(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    cluster_id: Optional[str] = Query(None),
):
    svc = K8sSecurityService(db)
    stats = await svc.get_stats(tenant_id, cluster_id=cluster_id)
    return APIResponse(data=stats)


@router.get("/findings")
async def list_findings(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    cluster_id: Optional[str] = Query(None),
    category: Optional[str]   = Query(None),
    severity: Optional[str]   = Query(None),
    status: Optional[str]     = Query(None, description="open|resolved|suppressed"),
    scan_id: Optional[str]    = Query(None),
    page: int                 = Query(1, ge=1),
    page_size: int            = Query(20, ge=1, le=100),
):
    svc = K8sSecurityService(db)
    result = await svc.get_findings(
        tenant_id,
        cluster_id=cluster_id,
        category=category,
        severity=severity,
        status=status,
        scan_id=scan_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=result["data"],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        pages=result["pages"],
    )


@router.patch("/findings/{finding_id}/suppress")
async def suppress_finding(
    finding_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    svc = K8sSecurityService(db)
    try:
        f = await svc.suppress_finding(tenant_id, finding_id)
        return APIResponse(data=f.to_dict(), message="Finding suppressed")
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/findings/{finding_id}/resolve")
async def resolve_finding(
    finding_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    svc = K8sSecurityService(db)
    try:
        f = await svc.resolve_finding(tenant_id, finding_id)
        return APIResponse(data=f.to_dict(), message="Finding resolved")
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
