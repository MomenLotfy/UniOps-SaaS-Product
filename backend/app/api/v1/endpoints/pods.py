from __future__ import annotations
"""Pods API — Kubernetes pod management, restart, delete, exec, scale and event inspection."""
from typing import Optional
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from app.api.deps import CurrentUser, DevOpsUser, TenantID, DBSession
from app.core.rate_limit import rate_limit
from app.schemas.pod import PodResponse, PodStats, PodActionResult
from app.schemas.common import APIResponse, PaginatedResponse
from app.core.exceptions import NotFoundError, IntegrationUnavailableError
from app.services.kubernetes_service import KubernetesService

router = APIRouter()


@router.get("", response_model=APIResponse[PaginatedResponse])
async def list_pods(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    namespace: Optional[str] = Query(None),
    cluster: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    svc = KubernetesService(db)
    result = await svc.list_pods(tenant_id, page, page_size, namespace, cluster, status)
    return APIResponse(data=result)


@router.get("/stats", response_model=APIResponse[PodStats])
async def get_pod_stats(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = KubernetesService(db)
    stats = await svc.get_stats(tenant_id)
    return APIResponse(data=stats)


@router.get("/namespaces")
async def get_namespaces(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = KubernetesService(db)
    namespaces = await svc.get_namespaces(tenant_id)
    return APIResponse(data=namespaces)


@router.get("/clusters")
async def get_clusters(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = KubernetesService(db)
    clusters = await svc.get_clusters(tenant_id)
    return APIResponse(data=clusters)


@router.get("/{pod_id}", response_model=APIResponse[PodResponse])
async def get_pod(pod_id: str, current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = KubernetesService(db)
    pod = await svc.get_pod(pod_id, tenant_id)
    return APIResponse(data=pod)


@router.get("/{pod_id}/events")
async def get_pod_events(pod_id: str, current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    """
    Fetch live Kubernetes events for a pod.
    Essential for debugging CrashLoopBackOff and OOMKilled pods.
    """
    svc = KubernetesService(db)
    events = await svc.get_pod_events(pod_id, tenant_id)
    return APIResponse(data=events)


@router.get("/{pod_id}/logs")
async def get_pod_logs(
    pod_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    tail: int = Query(default=200, le=1000),
    container: str | None = Query(default=None),
):
    """Stream last N log lines from a pod container via Kubernetes API."""
    svc = KubernetesService(db)
    content = await svc.get_pod_logs(pod_id, tenant_id, tail=tail, container=container)
    return APIResponse(data={"content": content, "pod_id": pod_id})


@router.post(
    "/{pod_id}/restart",
    response_model=APIResponse[PodActionResult],
    dependencies=[Depends(rate_limit("pod.restart", 30, 60))],
)
async def restart_pod(pod_id: str, current_user: DevOpsUser, tenant_id: TenantID, db: DBSession):
    """
    Gracefully restart a pod (grace_period=30s).
    If the pod is owned by a Deployment/StatefulSet/DaemonSet, the controller
    will schedule a replacement immediately.
    Requires: admin or devops role.
    """
    svc = KubernetesService(db)
    result = await svc.restart_pod(pod_id, tenant_id, current_user["user_id"])
    return APIResponse(data=result, message=result.message)


@router.delete(
    "/{pod_id}",
    response_model=APIResponse[PodActionResult],
    dependencies=[Depends(rate_limit("pod.delete", 20, 60))],
)
async def delete_pod(pod_id: str, current_user: DevOpsUser, tenant_id: TenantID, db: DBSession):
    """
    Force-delete a pod immediately (grace_period=0).
    Use restart for graceful termination; use delete for stuck/evicted pods.
    Requires: admin or devops role.
    """
    svc = KubernetesService(db)
    result = await svc.delete_pod(pod_id, tenant_id, current_user["user_id"])
    return APIResponse(data=result, message=result.message)



# ── Exec ──────────────────────────────────────────────────────────────────────
class ExecRequest(BaseModel):
    command: str
    container: str | None = None


@router.post(
    "/{pod_id}/exec",
    dependencies=[Depends(rate_limit("pod.exec", 10, 60))],
)
async def exec_pod(
    pod_id: str,
    body: ExecRequest,
    current_user: DevOpsUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """
    Execute a command in a running pod container (NO shell — safe arg vector).
    Returns stdout/stderr combined.  High-risk: rate-limited + fully audited.
    Requires: admin or devops role.
    """
    svc = KubernetesService(db)
    output = await svc.exec_pod(
        pod_id=pod_id,
        tenant_id=tenant_id,
        command=body.command,
        container=body.container,
        executed_by=current_user["user_id"],
    )
    return APIResponse(data={"output": output})


# ── Scale Deployment ──────────────────────────────────────────────────────────
class ScaleRequest(BaseModel):
    replicas: int
    namespace: str = "default"
    cluster: str | None = None


@router.post(
    "/deployments/{deployment_name}/scale",
    dependencies=[Depends(rate_limit("deployment.scale", 20, 60))],
)
async def scale_deployment(
    deployment_name: str,
    body: ScaleRequest,
    current_user: DevOpsUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """
    Scale a Kubernetes Deployment to the specified number of replicas.
    Requires: admin or devops role.
    """
    svc = KubernetesService(db)
    result = await svc.scale_deployment(
        tenant_id=tenant_id,
        deployment_name=deployment_name,
        namespace=body.namespace,
        replicas=body.replicas,
        triggered_by=current_user["user_id"],
        cluster=body.cluster,
    )
    return APIResponse(
        data=result,
        message=(
            f"Scaled {deployment_name} to {body.replicas} replica(s)"
            if result.get("success")
            else result.get("error", "Scale failed")
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER-LEVEL VISIBILITY ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/workloads/deployments")
async def list_deployments(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(
        None, description="Scope to a specific cluster owned by this tenant"
    ),
):
    """List Deployments — with replica status and rollout health."""
    svc = KubernetesService(db)
    # BUG-009: distinguish "cluster has none" from "cluster unreachable"
    result = await svc.list_cluster_resource(
        tenant_id,
        lambda c, ns: c.list_deployments(ns),
        namespace=namespace,
        cluster_id=cluster_id,
        resource="deployments",
    )
    return APIResponse(data=result)


@router.get("/workloads/statefulsets")
async def list_statefulsets(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(
        None, description="Scope to a specific cluster owned by this tenant"
    ),
):
    """List StatefulSets."""
    svc = KubernetesService(db)
    # BUG-009: distinguish "cluster has none" from "cluster unreachable"
    result = await svc.list_cluster_resource(
        tenant_id,
        lambda c, ns: c.list_statefulsets(ns),
        namespace=namespace,
        cluster_id=cluster_id,
        resource="statefulsets",
    )
    return APIResponse(data=result)


@router.get("/workloads/daemonsets")
async def list_daemonsets(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(
        None, description="Scope to a specific cluster owned by this tenant"
    ),
):
    """List DaemonSets."""
    svc = KubernetesService(db)
    # BUG-009: distinguish "cluster has none" from "cluster unreachable"
    result = await svc.list_cluster_resource(
        tenant_id,
        lambda c, ns: c.list_daemonsets(ns),
        namespace=namespace,
        cluster_id=cluster_id,
        resource="daemonsets",
    )
    return APIResponse(data=result)


@router.get("/network/services")
async def list_services(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(
        None, description="Scope to a specific cluster owned by this tenant"
    ),
):
    """List Services — ClusterIP, NodePort, LoadBalancer with external IPs."""
    svc = KubernetesService(db)
    # BUG-009: distinguish "cluster has none" from "cluster unreachable"
    result = await svc.list_cluster_resource(
        tenant_id,
        lambda c, ns: c.list_services(ns),
        namespace=namespace,
        cluster_id=cluster_id,
        resource="services",
    )
    return APIResponse(data=result)


@router.get("/network/ingresses")
async def list_ingresses(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(
        None, description="Scope to a specific cluster owned by this tenant"
    ),
):
    """List Ingresses — with routing rules and TLS config."""
    svc = KubernetesService(db)
    # BUG-009: distinguish "cluster has none" from "cluster unreachable"
    result = await svc.list_cluster_resource(
        tenant_id,
        lambda c, ns: c.list_ingresses(ns),
        namespace=namespace,
        cluster_id=cluster_id,
        resource="ingresses",
    )
    return APIResponse(data=result)


@router.get("/batch/jobs")
async def list_jobs(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(
        None, description="Scope to a specific cluster owned by this tenant"
    ),
):
    """List Jobs and CronJobs."""
    svc = KubernetesService(db)
    # BUG-009: distinguish "cluster has none" from "cluster unreachable"
    result = await svc.list_cluster_resource(
        tenant_id,
        lambda c, ns: c.list_jobs(ns),
        namespace=namespace,
        cluster_id=cluster_id,
        resource="jobs",
    )
    return APIResponse(data=result)


@router.get("/config/configmaps")
async def list_configmaps(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(
        None, description="Scope to a specific cluster owned by this tenant"
    ),
):
    """List ConfigMaps — keys only, never values."""
    svc = KubernetesService(db)
    # BUG-009: distinguish "cluster has none" from "cluster unreachable"
    result = await svc.list_cluster_resource(
        tenant_id,
        lambda c, ns: c.list_configmaps(ns),
        namespace=namespace,
        cluster_id=cluster_id,
        resource="configmaps",
    )
    return APIResponse(data=result)


@router.get("/config/secrets")
async def list_secrets_metadata(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(
        None, description="Scope to a specific cluster owned by this tenant"
    ),
):
    """List Secrets — metadata + key names ONLY. Values are never returned."""
    svc = KubernetesService(db)
    # BUG-009: distinguish "cluster has none" from "cluster unreachable"
    result = await svc.list_cluster_resource(
        tenant_id,
        lambda c, ns: c.list_secrets_metadata(ns),
        namespace=namespace,
        cluster_id=cluster_id,
        resource="secrets",
    )
    return APIResponse(data=result)


@router.get("/autoscaling/hpa")
async def list_hpa(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(
        None, description="Scope to a specific cluster owned by this tenant"
    ),
):
    """List Horizontal Pod Autoscalers — current vs desired replicas + CPU%."""
    svc = KubernetesService(db)
    # BUG-009: distinguish "cluster has none" from "cluster unreachable"
    result = await svc.list_cluster_resource(
        tenant_id,
        lambda c, ns: c.list_hpa(ns),
        namespace=namespace,
        cluster_id=cluster_id,
        resource="hpa",
    )
    return APIResponse(data=result)


@router.get("/cluster/summary")
async def cluster_summary(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(
        None, description="Scope to a specific cluster owned by this tenant"
    ),
):
    """
    One-shot cluster overview:
    pods + deployments + services + ingresses + jobs + configmaps + hpa counts.
    Used by the Cluster Overview tab.
    """
    import asyncio
    svc = KubernetesService(db)
    try:
        client = await svc.get_client_for_cluster(tenant_id, cluster_id)
    except NotFoundError:
        raise
    except IntegrationUnavailableError:
        client = None
    if not client:
        return APIResponse(data={
            "connected": False,
            "source":    "unavailable",
            "degraded":  True,
            "message":   "No Kubernetes integration connected for this tenant",
        })

    # BUG-009: `connected: True` used to be asserted merely because a client
    # object could be built. When the API server was down every list_* below
    # returned [] and the summary reported a healthy cluster with 0 of
    # everything. Reachability is now verified before any count is trusted.
    reachable, reason = await client.check_reachable()
    if not reachable:
        return APIResponse(data={
            "connected":  False,
            "source":     "unavailable",
            "degraded":   True,
            "error_code": "KUBERNETES_UNAVAILABLE",
            "message":    f"Kubernetes unavailable: {reason}",
            "counts":     {},
        })

    # Fetch all in parallel
    (deps, sts, ds, svcs, ings, jobs, cms, hpas) = await asyncio.gather(
        client.list_deployments(namespace),
        client.list_statefulsets(namespace),
        client.list_daemonsets(namespace),
        client.list_services(namespace),
        client.list_ingresses(namespace),
        client.list_jobs(namespace),
        client.list_configmaps(namespace),
        client.list_hpa(namespace),
        return_exceptions=True,
    )

    def _safe(val):
        return val if isinstance(val, list) else []

    return APIResponse(data={
        "connected":   True,
        "source":      "kubernetes",
        "degraded":    False,
        "deployments": _safe(deps),
        "statefulsets":_safe(sts),
        "daemonsets":  _safe(ds),
        "services":    _safe(svcs),
        "ingresses":   _safe(ings),
        "jobs":        _safe(jobs),
        "configmaps":  _safe(cms),
        "hpa":         _safe(hpas),
        "counts": {
            "deployments": len(_safe(deps)),
            "statefulsets":len(_safe(sts)),
            "daemonsets":  len(_safe(ds)),
            "services":    len(_safe(svcs)),
            "ingresses":   len(_safe(ings)),
            "jobs":        len(_safe(jobs)),
            "configmaps":  len(_safe(cms)),
            "hpa":         len(_safe(hpas)),
        },
    })
