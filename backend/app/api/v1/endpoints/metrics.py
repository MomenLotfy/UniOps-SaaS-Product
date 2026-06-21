from __future__ import annotations
"""
Metrics API — Module 1 of Epic 9.

GET /api/v1/metrics/pods/{pod_id}
  → Real metrics via Prometheus when configured
  → Fallback to K8s Metrics Server snapshot + synthetic time-series

Response shape (matches frontend contract):
  {
    "pod_id": "abc",
    "pod_name": "my-pod",
    "namespace": "default",
    "source": "prometheus | k8s_metrics | synthetic",
    "points": [
      {"timestamp": "...", "cpu": 32.5, "memory": 48.1}
    ]
  }
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
    """
    Per-pod CPU + Memory timeseries.

    Data source priority:
      1. Prometheus (when prometheus integration exists + server_url set)
      2. K8s Metrics Server snapshot (instantaneous → synthetic series)
      3. Synthetic data seeded by pod_id
    """
    pod = await _load_pod(pod_id, tenant_id, db)

    pod_name  = pod.name      if pod else pod_id
    namespace = pod.namespace if pod else "default"

    # ── Try Prometheus ────────────────────────────────────────────────────────
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

    # ── Fallback: K8s Metrics Server snapshot → synthetic series ─────────────
    points = await _metrics_server_or_synthetic(pod, pod_id, pod_name, namespace, tenant_id, db, hours)

    return APIResponse(data={
        "pod_id":    pod_id,
        "pod_name":  pod_name,
        "namespace": namespace,
        "source":    points["source"],
        "points":    points["data"],
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
    Cluster-wide CPU + Memory — Prometheus-backed with K8s fallback.
    Compatible with existing /observability/metrics/cluster shape.
    """
    prometheus_integration = await _get_integration(db, tenant_id, "prometheus")
    cpu_pct = mem_pct = 0.0
    source  = "synthetic"

    if prometheus_integration:
        from app.integrations.observability.prometheus import get_prometheus_client
        client = get_prometheus_client(prometheus_integration)
        if client and await client.health():
            try:
                cpu_pct = await client.get_cluster_cpu_pct()
                mem_pct = await client.get_cluster_memory_pct()
                source  = "prometheus"
            except Exception as exc:
                logger.warning(f"[metrics] cluster Prometheus query failed: {exc}")

    if source == "synthetic":
        from app.services.kubernetes_service import KubernetesService
        try:
            svc   = KubernetesService(db)
            stats = await svc.get_stats(tenant_id)
            if stats:
                cpu_pct = stats.cpu_usage_pct or 0.0
                mem_pct = stats.memory_usage_pct or 0.0
                source  = "k8s_metrics"
        except Exception:
            pass

    from app.integrations.observability.prometheus import _synthetic_pod_metrics
    import math, random
    seed = sum(ord(c) for c in tenant_id)

    def _ts(base: float, s: int) -> list[dict]:
        rng  = random.Random(s)
        from datetime import datetime, timezone, timedelta
        now  = datetime.now(timezone.utc)
        pts  = 30
        res  = []
        for i in range(pts):
            ts   = now - timedelta(minutes=2 * (pts - i - 1))
            phase = (i / pts) * 2 * math.pi
            val  = max(0.0, min(100.0, base + math.sin(phase) * base * 0.15
                                + rng.uniform(-3, 3)))
            res.append({
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "value":     round(val, 1),
            })
        return res

    return APIResponse(data={
        "source": source,
        "cpu":    {"current_pct": round(cpu_pct, 1), "timeseries": _ts(cpu_pct, seed + 1)},
        "memory": {"current_pct": round(mem_pct, 1), "timeseries": _ts(mem_pct, seed + 2)},
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_pod(pod_id: str, tenant_id: str, db) -> Optional[object]:
    try:
        from app.models.pod import Pod
        result = await db.execute(
            select(Pod).where(Pod.id == pod_id, Pod.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()
    except Exception:
        return None


async def _get_integration(db, tenant_id: str, provider: str) -> Optional[dict]:
    try:
        result = await db.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.provider == provider,
                Integration.is_active == True,
            )
        )
        rec = result.scalar_one_or_none()
        if not rec:
            return None
        return {
            "config":      rec.config or {},
            "credentials": rec.credentials or {},
        }
    except Exception:
        return None


async def _metrics_server_or_synthetic(
    pod, pod_id: str, pod_name: str, namespace: str,
    tenant_id: str, db, hours: int
) -> dict:
    """Try K8s Metrics Server snapshot, fall back to synthetic."""
    cpu_pct = mem_pct = 0.0
    source  = "synthetic"

    if pod:
        try:
            cpu_pct = float(getattr(pod, "cpu_usage_pct",  0) or 0)
            mem_pct = float(getattr(pod, "memory_usage_pct", 0) or 0)
            if cpu_pct or mem_pct:
                source = "k8s_metrics"
        except Exception:
            pass

    from app.integrations.observability.prometheus import _synthetic_pod_metrics
    import math, random
    from datetime import datetime, timezone, timedelta

    seed   = sum(ord(c) for c in pod_id)
    rng    = random.Random(seed)
    points = min(hours * 30, 60)
    now    = datetime.now(timezone.utc)
    step_m = max(1, (hours * 60) // points)

    base_cpu = cpu_pct or rng.uniform(5, 70)
    base_mem = mem_pct or rng.uniform(20, 80)

    data = []
    for i in range(points):
        ts    = now - timedelta(minutes=step_m * (points - i - 1))
        phase = (i / points) * 2 * math.pi
        c     = max(0.0, min(100.0, base_cpu + math.sin(phase) * base_cpu * 0.2
                              + rng.uniform(-3, 3)))
        m     = max(0.0, min(100.0, base_mem + math.sin(phase + 1) * base_mem * 0.1
                              + rng.uniform(-2, 2)))
        data.append({
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cpu":       round(c, 1),
            "memory":    round(m, 1),
        })

    return {"source": source, "data": data}
