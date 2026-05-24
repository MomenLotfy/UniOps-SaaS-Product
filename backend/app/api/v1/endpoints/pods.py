from __future__ import annotations
"""Pods API — Kubernetes pod management, restart, delete, exec, scale and event inspection."""
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession
from app.schemas.pod import PodResponse, PodStats, PodActionResult
from app.schemas.common import APIResponse, PaginatedResponse
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
async def get_pod(pod_id: str, current_user: CurrentUser, db: DBSession):
    svc = KubernetesService(db)
    pod = await svc.get_pod(pod_id)
    return APIResponse(data=pod)


@router.get("/{pod_id}/events")
async def get_pod_events(pod_id: str, current_user: CurrentUser, db: DBSession):
    """
    Fetch live Kubernetes events for a pod.
    Essential for debugging CrashLoopBackOff and OOMKilled pods.
    """
    svc = KubernetesService(db)
    events = await svc.get_pod_events(pod_id)
    return APIResponse(data=events)


@router.get("/{pod_id}/logs")
async def get_pod_logs(
    pod_id: str,
    current_user: CurrentUser,
    db: DBSession,
    tail: int = Query(default=200, le=1000),
    container: str | None = Query(default=None),
):
    """Stream last N log lines from a pod container via Kubernetes API."""
    svc = KubernetesService(db)
    content = await svc.get_pod_logs(pod_id, tail=tail, container=container)
    return APIResponse(data={"content": content, "pod_id": pod_id})


@router.post("/{pod_id}/restart", response_model=APIResponse[PodActionResult])
async def restart_pod(pod_id: str, current_user: AdminUser, db: DBSession):
    """
    Gracefully restart a pod (grace_period=30s).
    If the pod is owned by a Deployment/StatefulSet/DaemonSet, the controller
    will schedule a replacement immediately.
    Requires: admin or devops role.
    """
    svc = KubernetesService(db)
    result = await svc.restart_pod(pod_id, current_user["user_id"])
    return APIResponse(data=result, message=result.message)


@router.delete("/{pod_id}", response_model=APIResponse[PodActionResult])
async def delete_pod(pod_id: str, current_user: AdminUser, db: DBSession):
    """
    Force-delete a pod immediately (grace_period=0).
    Use restart for graceful termination; use delete for stuck/evicted pods.
    Requires: admin role.
    """
    svc = KubernetesService(db)
    result = await svc.delete_pod(pod_id, current_user["user_id"])
    return APIResponse(data=result, message=result.message)



# ── Exec ──────────────────────────────────────────────────────────────────────
class ExecRequest(BaseModel):
    command: str
    container: str | None = None


@router.post("/{pod_id}/exec")
async def exec_pod(
    pod_id: str,
    body: ExecRequest,
    current_user: AdminUser,
    db: DBSession,
):
    """
    Execute a command in a running pod container.
    Returns stdout/stderr combined.
    Requires: admin or devops role.
    """
    svc = KubernetesService(db)
    output = await svc.exec_pod(
        pod_id=pod_id,
        command=body.command,
        container=body.container,
    )
    return APIResponse(data={"output": output})


# ── Scale Deployment ──────────────────────────────────────────────────────────
class ScaleRequest(BaseModel):
    replicas: int
    namespace: str = "default"


@router.post("/deployments/{deployment_name}/scale")
async def scale_deployment(
    deployment_name: str,
    body: ScaleRequest,
    current_user: AdminUser,
    db: DBSession,
):
    """
    Scale a Kubernetes Deployment to the specified number of replicas.
    Requires: admin or devops role.
    """
    svc = KubernetesService(db)
    result = await svc.scale_deployment(
        deployment_name=deployment_name,
        namespace=body.namespace,
        replicas=body.replicas,
        triggered_by=current_user["user_id"],
    )
    return APIResponse(
        data=result,
        message=f"Scaled {deployment_name} to {body.replicas} replica(s)",
    )


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER-LEVEL VISIBILITY ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/workloads/deployments")
async def list_deployments(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    """List Deployments — with replica status and rollout health."""
    svc    = KubernetesService(db)
    client = await svc._get_k8s_client(tenant_id)
    if not client:
        return APIResponse(data=[])
    data = await client.list_deployments(namespace)
    return APIResponse(data=data)


@router.get("/workloads/statefulsets")
async def list_statefulsets(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    """List StatefulSets."""
    svc    = KubernetesService(db)
    client = await svc._get_k8s_client(tenant_id)
    if not client:
        return APIResponse(data=[])
    return APIResponse(data=await client.list_statefulsets(namespace))


@router.get("/workloads/daemonsets")
async def list_daemonsets(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    """List DaemonSets."""
    svc    = KubernetesService(db)
    client = await svc._get_k8s_client(tenant_id)
    if not client:
        return APIResponse(data=[])
    return APIResponse(data=await client.list_daemonsets(namespace))


@router.get("/network/services")
async def list_services(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    """List Services — ClusterIP, NodePort, LoadBalancer with external IPs."""
    svc    = KubernetesService(db)
    client = await svc._get_k8s_client(tenant_id)
    if not client:
        return APIResponse(data=[])
    return APIResponse(data=await client.list_services(namespace))


@router.get("/network/ingresses")
async def list_ingresses(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    """List Ingresses — with routing rules and TLS config."""
    svc    = KubernetesService(db)
    client = await svc._get_k8s_client(tenant_id)
    if not client:
        return APIResponse(data=[])
    return APIResponse(data=await client.list_ingresses(namespace))


@router.get("/batch/jobs")
async def list_jobs(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    """List Jobs and CronJobs."""
    svc    = KubernetesService(db)
    client = await svc._get_k8s_client(tenant_id)
    if not client:
        return APIResponse(data=[])
    return APIResponse(data=await client.list_jobs(namespace))


@router.get("/config/configmaps")
async def list_configmaps(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    """List ConfigMaps — keys only, never values."""
    svc    = KubernetesService(db)
    client = await svc._get_k8s_client(tenant_id)
    if not client:
        return APIResponse(data=[])
    return APIResponse(data=await client.list_configmaps(namespace))


@router.get("/config/secrets")
async def list_secrets_metadata(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    """List Secrets — metadata + key names ONLY. Values are never returned."""
    svc    = KubernetesService(db)
    client = await svc._get_k8s_client(tenant_id)
    if not client:
        return APIResponse(data=[])
    return APIResponse(data=await client.list_secrets_metadata(namespace))


@router.get("/autoscaling/hpa")
async def list_hpa(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    """List Horizontal Pod Autoscalers — current vs desired replicas + CPU%."""
    svc    = KubernetesService(db)
    client = await svc._get_k8s_client(tenant_id)
    if not client:
        return APIResponse(data=[])
    return APIResponse(data=await client.list_hpa(namespace))


@router.get("/cluster/summary")
async def cluster_summary(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
):
    """
    One-shot cluster overview:
    pods + deployments + services + ingresses + jobs + configmaps + hpa counts.
    Used by the Cluster Overview tab.
    """
    import asyncio
    svc    = KubernetesService(db)
    client = await svc._get_k8s_client(tenant_id)
    if not client:
        return APIResponse(data={"connected": False})

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
