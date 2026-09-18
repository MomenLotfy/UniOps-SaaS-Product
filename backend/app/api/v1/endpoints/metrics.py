from __future__ import annotations
"""
Metrics API — per-pod and cluster CPU/Memory.

Data sources (in priority order):
  1. Prometheus (when a 'prometheus' integration exists for the tenant)
  2. Kubernetes Metrics Server snapshot via the tenant's K8s integration

NO synthetic data.  When no backend can serve real data the response carries
``source: "unavailable"`` with null/empty values so the UI can render an
explicit "Not Connected / Unavailable" state instead of fake charts.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.models.pod import Pod
from app.models.integration import Integration

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/pods/{pod_id}")
async def get_pod_metrics(
    pod_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    hours: int = Query(1, ge=1, le=72, description="Time range in hours"),
    step: str = Query("60s", pattern=r"^\d+[smh]$", description="Resolution step"),
    cluster_id: Optional[str] = Query(None),
):
    """Per-pod CPU + Memory timeseries — Prometheus-backed or unavailable."""
    pod = await _load_pod(pod_id, tenant_id, db)
    if pod is None:
        raise HTTPException(status_code=404, detail="Pod not found")

    pod_name  = pod.name
    namespace = pod.namespace or "default"

    prometheus_integration = await _get_integration(db, tenant_id, "prometheus")
    if prometheus_integration:
        from app.integrations.observability.prometheus import get_prometheus_client
        client = get_prometheus_client(prometheus_integration)
        if client and await client.health():
            try:
                points = await client.get_pod_metrics(
                    pod_name, namespace, duration_hours=hours, step=step
                )
                if points:
                    return APIResponse(data={
                        "pod_id":    pod_id,
                        "pod_name":  pod_name,
                        "namespace": namespace,
                        "source":    "prometheus",
                        "points":    points,
                    })
            except Exception as exc:
                logger.warning(f"[metrics] Prometheus query failed: {exc}")

    # K8s Metrics Server current snapshot — real but instantaneous (no history)
    snapshot = await _metrics_server_snapshot(pod_name, namespace, tenant_id, db)
    if snapshot is not None:
        return APIResponse(data={
            "pod_id":    pod_id,
            "pod_name":  pod_name,
            "namespace": namespace,
            "source":    "k8s_metrics",
            "points":    [snapshot],   # single real current reading
        })

    # No metrics backend at all — explicit unavailable state
    return APIResponse(data={
        "pod_id":    pod_id,
        "pod_name":  pod_name,
        "namespace": namespace,
        "source":    "unavailable",
        "points":    [],
        "message":   "No metrics backend connected (prometheus or metrics-server)",
    })


@router.get("/cluster")
async def get_cluster_metrics_v2(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    hours: int = Query(1, ge=1, le=72),
    cluster_id: Optional[str] = Query(None),
):
    """
    Cluster-wide CPU + Memory averages over `hours`.
    Prometheus-backed; metrics-server snapshot otherwise; 'unavailable' state
    with nulls when neither exists.  Compatible with the
    /observability/metrics/cluster response shape (cpu/memory blocks).
    """
    from app.integrations.observability.prometheus import get_prometheus_client

    prometheus_integration = await _get_integration(db, tenant_id, "prometheus")
    if prometheus_integration:
        client = get_prometheus_client(prometheus_integration)
        if client and await client.health():
            try:
                cpu_series = await client.get_cluster_cpu_series(hours=hours)
                mem_series = await client.get_cluster_memory_series(hours=hours)
                if cpu_series or mem_series:
                    cpu_cur = cpu_series[-1]["value"] if cpu_series else None
                    mem_cur = mem_series[-1]["value"] if mem_series else None
                    return APIResponse(data={
                        "source": "prometheus",
                        "cpu":    {"current_pct": cpu_cur, "timeseries": cpu_series},
                        "memory": {"current_pct": mem_cur, "timeseries": mem_series},
                    })
            except Exception as exc:
                logger.warning(f"[metrics] cluster Prometheus query failed: {exc}")

    # Metrics-server snapshot via the tenant K8s integration — real current values
    snapshot = await _cluster_metrics_server_snapshot(tenant_id, db)
    if snapshot is not None:
        return APIResponse(data={
            "source": "k8s_metrics",
            "cpu":    {"current_pct": snapshot.get("cpu_pct"),    "timeseries": []},
            "memory": {"current_pct": snapshot.get("memory_pct"), "timeseries": []},
        })

    return APIResponse(data={
        "source": "unavailable",
        "cpu":    {"current_pct": None, "timeseries": []},
        "memory": {"current_pct": None, "timeseries": []},
        "message": "No metrics backend connected (prometheus or metrics-server)",
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_pod(pod_id: str, tenant_id: str, db) -> Optional[Pod]:
    try:
        result = await db.execute(
            select(Pod).where(Pod.id == pod_id, Pod.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()
    except Exception:
        return None


async def _get_integration(db, tenant_id: str, itype: str) -> Optional[dict]:
    """Return {config, credentials} for a tenant integration of the given type."""
    try:
        result = await db.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.type      == itype,
                Integration.is_active == True,
                Integration.status    == "connected",
            )
        )
        rec = result.scalar_one_or_none()
        if not rec:
            return None
        return {
            "config":      rec.config or {},
            "credentials": _decrypt_creds(rec.credentials or {}),
        }
    except Exception:
        return None


def _decrypt_creds(creds: dict) -> dict:
    from app.utils.encryption import decrypt
    out = {}
    for k, v in creds.items():
        try:
            out[k] = decrypt(v)
        except Exception:
            out[k] = v
    return out


async def _metrics_server_snapshot(
    pod_name: str, namespace: str, tenant_id: str, db
) -> Optional[dict]:
    """Instantaneous metrics-server reading for a pod, if reachable."""
    try:
        from app.services.kubernetes_service import KubernetesService
        svc    = KubernetesService(db)
        client = await svc.get_k8s_client_for_tenant(tenant_id)
        if not client:
            return None
        metrics = await client.get_pod_metrics(namespace)
        m = metrics.get(pod_name) if metrics else None
        if not m:
            return None
        from datetime import datetime, timezone
        cpu    = m.get("cpu_usage")        # cores
        memory = m.get("memory_usage")     # bytes
        if cpu is None and memory is None:
            return None
        return {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cpu":       round(cpu or 0.0, 4),
            "memory":    memory or 0,
        }
    except Exception as exc:
        logger.debug(f"[metrics] metrics-server snapshot failed: {exc}")
        return None


async def _cluster_metrics_server_snapshot(tenant_id: str, db) -> Optional[dict]:
    """Cluster-average cpu/memory % from live node metrics, if reachable."""
    try:
        from app.services.kubernetes_service import KubernetesService
        svc    = KubernetesService(db)
        client = await svc.get_k8s_client_for_tenant(tenant_id)
        if not client:
            return None
        nodes = await client.get_node_metrics()
        if not nodes:
            return None
        # average across nodes that reported values
        cpus = [n["cpu_usage"]    for n in nodes if n.get("cpu_usage")    is not None]
        mems = [n["memory_usage"] for n in nodes if n.get("memory_usage") is not None]
        return {
            "cpu_pct":    round(sum(cpus) / len(cpus), 1) if cpus else None,
            "memory_pct": round(sum(mems) / len(mems), 1) if mems else None,
        }
    except Exception as exc:
        logger.debug(f"[metrics] cluster metrics-server snapshot failed: {exc}")
        return None
