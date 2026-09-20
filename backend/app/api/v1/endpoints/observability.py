from __future__ import annotations
"""
Observability API — Metrics + Logs for DevOps Center.

Metrics:
  - Time-series come from Prometheus (real query_range data) when a
    'prometheus' integration is connected for the tenant.
  - Current-snapshot values come from the Kubernetes Metrics Server (real)
    when a 'kubernetes' integration is connected.
  - When neither is available the response carries source="unavailable"
    with null values and empty series — the UI renders an explicit
    "Not Connected / Unavailable" state.  NO synthetic series are generated.

Logs:
   Proxies to the K8s log read with search/filter/level support.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.services.kubernetes_service import KubernetesService

router = APIRouter()
logger = logging.getLogger(__name__)


RANGE_HOURS = {
    "15m": (0.25, "30s"),
    "1h":  (1,    "60s"),
    "6h":  (6,    "300s"),
    "24h": (24,   "900s"),
    "7d":  (168,  "3600s"),
    "30d": (720,  "21600s"),
}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/metrics/cluster")
async def get_cluster_metrics(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    range: str = Query("1h", pattern="^(15m|1h|6h|24h|7d|30d)$"),
    namespace: Optional[str] = Query(None),
):
    """Cluster-level CPU + Memory — Prometheus timeseries or explicit unavailable."""
    from app.integrations.observability.prometheus import get_prometheus_client

    hours, step = RANGE_HOURS.get(range, RANGE_HOURS["1h"])
    step = f"{int(step[:-1])}{step[-1]}"
    hours_i = max(1, int(hours)) if hours >= 1 else 1

    integration = await _get_typed_integration(db, tenant_id, "prometheus")
    if integration:
        client = get_prometheus_client(integration)
        if client and await client.health():
            try:
                cpu_series = await client.get_cluster_cpu_series(
                    hours=hours_i, step=step, namespace=namespace)
                mem_series = await client.get_cluster_memory_series(
                    hours=hours_i, step=step, namespace=namespace)
                if cpu_series or mem_series:
                    return APIResponse(data={
                        "range":  range,
                        "source": "prometheus",
                        "cpu":    {
                            "current_pct": cpu_series[-1]["value"] if cpu_series else None,
                            "timeseries":  cpu_series,
                        },
                        "memory": {
                            "current_pct": mem_series[-1]["value"] if mem_series else None,
                            "timeseries":  mem_series,
                        },
                    })
            except Exception as exc:
                logger.warning(f"[obs:metrics] prometheus query failed: {exc}")

    # K8s metrics-server snapshot — real instant values, no history
    snapshot = await _live_cluster_snapshot(tenant_id, db, namespace)
    if snapshot is not None:
        return APIResponse(data={
            "range":  range,
            "source": "k8s_metrics",
            "cpu":    {"current_pct": snapshot.get("cpu_pct"),    "timeseries": []},
            "memory": {"current_pct": snapshot.get("memory_pct"), "timeseries": []},
        })

    return APIResponse(data={
        "range":  range,
        "source": "unavailable",
        "cpu":    {"current_pct": None, "timeseries": []},
        "memory": {"current_pct": None, "timeseries": []},
        "message": "No metrics backend connected (prometheus or metrics-server)",
    })


@router.get("/metrics/pods")
async def get_pod_metrics(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    range: str = Query("1h", pattern="^(15m|1h|6h|24h|7d|30d)$"),
    top: int = Query(10, ge=1, le=50),
):
    """
    Per-pod CPU + Memory snapshot. Current values come from the Pods table,
    which is kept fresh by the K8s pod sync (real metrics-server data).
    Time-series are only included when Prometheus is connected and returns data.
    """
    from app.integrations.observability.prometheus import get_prometheus_client

    hours, step = RANGE_HOURS.get(range, RANGE_HOURS["1h"])
    step = f"{int(step[:-1])}{step[-1]}"
    hours_i = max(1, int(hours)) if hours >= 1 else 1

    prometheus_client = None
    integration = await _get_typed_integration(db, tenant_id, "prometheus")
    if integration:
        c = get_prometheus_client(integration)
        if c and await c.health():
            prometheus_client = c

    svc = KubernetesService(db)
    try:
        result = await svc.list_pods(tenant_id, 1, max(top, 100), namespace)
        pods_raw = result.data if hasattr(result, "data") else (result or [])
    except Exception:
        pods_raw = []

    source = "prometheus" if prometheus_client else ("k8s_metrics" if pods_raw else "unavailable")

    pod_list = []
    for p in pods_raw[:top]:
        # BUG-P1-OBS-01: PodResponse is a pydantic BaseModel, which has no
        # to_dict() — the old fallback silently produced {} for every pod, so
        # the whole panel rendered as name="unknown"/status="Unknown".
        if isinstance(p, dict):
            pod_dict = p
        elif hasattr(p, "model_dump"):
            pod_dict = p.model_dump()
        elif hasattr(p, "to_dict"):
            pod_dict = p.to_dict()
        else:
            pod_dict = {}
        name = pod_dict.get("name", "unknown")
        ns   = pod_dict.get("namespace", "default")

        cpu_ts = mem_ts = []
        cpu_cur = mem_cur = None

        if prometheus_client:
            # Real per-pod timeseries from Prometheus — cpu/mem in *percent* for parity
            try:
                cpu_ts = [
                    {"timestamp": pt["timestamp"], "value": pt["cpu"]}
                    for pt in await prometheus_client.get_pod_cpu_timeseries(
                        name, ns, duration_hours=hours_i, step=step)
                ]
            except Exception:
                cpu_ts = []
            try:
                mem_ts = [
                    {"timestamp": pt["timestamp"], "value": pt["memory"]}
                    for pt in await prometheus_client.get_pod_memory_timeseries(
                        name, ns, duration_hours=hours_i, step=step)
                ]
            except Exception:
                mem_ts = []

            if cpu_ts:
                cpu_cur = cpu_ts[-1]["value"]
            if mem_ts:
                mem_cur = mem_ts[-1]["value"]

        # DB-held current snapshot (from real K8s sync via metrics-server)
        cpu_u = pod_dict.get("cpu_usage")
        mem_u = pod_dict.get("memory_usage")
        cpu_l = pod_dict.get("cpu_limit")
        mem_l = pod_dict.get("memory_limit")
        if cpu_cur is None and cpu_u is not None and cpu_l:
            cpu_cur = round((cpu_u / cpu_l) * 100, 1)
        if mem_cur is None and mem_u is not None and mem_l:
            mem_cur = round((mem_u / mem_l) * 100, 1)

        pod_list.append({
            "name":              name,
            "namespace":         ns,
            "status":            pod_dict.get("status", "Unknown"),
            "cpu_pct":           cpu_cur,
            "memory_pct":        mem_cur,
            # BUG-011: the Restart Spikes panel filters pods by restart_count,
            # but this payload omitted it, so the panel always read empty.
            "restart_count":     pod_dict.get("restart_count", 0) or 0,
            "cpu_timeseries":    cpu_ts,
            "memory_timeseries": mem_ts,
        })

    pods_with_metrics = sum(
        1 for p in pod_list if p["cpu_pct"] is not None or p["memory_pct"] is not None
    )
    return APIResponse(data={
        "range":  range,
        "source": "unavailable" if pods_with_metrics == 0 else source,
        "pods":   pod_list,
    })


@router.get("/metrics/namespaces")
async def get_namespace_metrics(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    """Aggregate CPU + Memory per namespace — from real pod snapshot data only."""
    svc = KubernetesService(db)
    try:
        result = await svc.list_pods(tenant_id, 1, 200)
        pods_raw = result.data if hasattr(result, "data") else (result or [])
    except Exception:
        pods_raw = []

    ns_map: dict[str, dict] = {}
    for p in pods_raw:
        # Same BUG-P1-OBS-01 as /metrics/pods: PodResponse has no to_dict(), so
        # every pod collapsed into a single "default" namespace with null metrics.
        if isinstance(p, dict):
            pod_dict = p
        elif hasattr(p, "model_dump"):
            pod_dict = p.model_dump()
        elif hasattr(p, "to_dict"):
            pod_dict = p.to_dict()
        else:
            pod_dict = {}
        ns = pod_dict.get("namespace", "default")
        cpu_u = pod_dict.get("cpu_usage")
        mem_u = pod_dict.get("memory_usage")
        cpu_l = pod_dict.get("cpu_limit")
        mem_l = pod_dict.get("memory_limit")
        cpu_pct = (cpu_u / cpu_l * 100) if (cpu_u is not None and cpu_l) else None
        mem_pct = (mem_u / mem_l * 100) if (mem_u is not None and mem_l) else None

        entry = ns_map.setdefault(ns, {
            "namespace": ns, "pod_count": 0,
            "_cpu_sum": 0.0, "_cpu_n": 0, "_mem_sum": 0.0, "_mem_n": 0,
        })
        entry["pod_count"] += 1
        if cpu_pct is not None:
            entry["_cpu_sum"] += cpu_pct; entry["_cpu_n"] += 1
        if mem_pct is not None:
            entry["_mem_sum"] += mem_pct; entry["_mem_n"] += 1

    out = []
    for ns_data in ns_map.values():
        out.append({
            "namespace":   ns_data["namespace"],
            "pod_count":   ns_data["pod_count"],
            "cpu_pct":     round(ns_data["_cpu_sum"] / ns_data["_cpu_n"], 1)
                           if ns_data["_cpu_n"] else None,
            "memory_pct":  round(ns_data["_mem_sum"] / ns_data["_mem_n"], 1)
                           if ns_data["_mem_n"] else None,
            "has_metrics": bool(ns_data["_cpu_n"] or ns_data["_mem_n"]),
        })

    return APIResponse(data=out)


@router.get("/logs")
async def get_logs(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    namespace: Optional[str] = Query(None),
    pod: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    level: Optional[str] = Query(None),   # INFO | WARN | ERROR
    tail: int = Query(200, ge=10, le=1000),
):
    """
    Fetch and filter logs from a pod or namespace.
    Wraps the real K8s log read endpoint with search + level filtering.
    """
    if not pod:
        return APIResponse(data={
            "pod": None,
            "namespace": namespace,
            "lines": [],
            "total": 0,
            "filtered": 0,
            "message": "Select a pod to view its logs",
        })

    # Resolve pod by DB id OR "namespace/name"
    resolved = await _resolve_pod_ref(pod, tenant_id, db)
    if resolved is None:
        return APIResponse(data={
            "pod": pod,
            "namespace": namespace,
            "lines": [],
            "total": 0,
            "filtered": 0,
            "message": "Pod not found for this tenant",
        })

    svc = KubernetesService(db)
    try:
        log_result = await svc.get_pod_logs_by_name(
            tenant_id, resolved["name"], resolved["namespace"], tail)
        raw = log_result if isinstance(log_result, str) else str(log_result or "")
        log_source = "kubernetes"
    except Exception as e:
        logger.warning(f"[obs:logs] pod={pod} error={e}")
        raw, log_source = "", "unavailable"

    lines_raw = [l for l in raw.splitlines() if l.strip()]

    def detect_level(line: str) -> str:
        u = line.upper()
        if any(x in u for x in ["ERROR", "FATAL", "CRITICAL", "EXCEPTION", "TRACEBACK"]):
            return "ERROR"
        if any(x in u for x in ["WARN", "WARNING"]):
            return "WARN"
        return "INFO"

    def parse_timestamp(line: str) -> Optional[str]:
        import re
        m = re.match(r"^(\d{4}-\d{2}-\d{2}T[\d:.Z+\-]+)", line)
        return m.group(1) if m else None

    parsed = []
    for raw_line in lines_raw:
        lvl = detect_level(raw_line)
        ts  = parse_timestamp(raw_line)
        msg = raw_line[len(ts):].strip() if ts else raw_line
        parsed.append({"timestamp": ts, "level": lvl, "message": msg, "raw": raw_line})

    total = len(parsed)

    if level and level.upper() in ("INFO", "WARN", "ERROR"):
        parsed = [l for l in parsed if l["level"] == level.upper()]
    if search:
        s_lower = search.lower()
        parsed = [l for l in parsed if s_lower in l["raw"].lower()]

    return APIResponse(data={
        "pod":       f'{resolved["namespace"]}/{resolved["name"]}',
        "namespace": resolved["namespace"],
        "source":    log_source,
        "lines":     parsed[-tail:],
        "total":     total,
        "filtered":  len(parsed),
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_typed_integration(db, tenant_id: str, itype: str):
    """Return {config, credentials} for a tenant integration by type."""
    from sqlalchemy import select as _sel
    from app.models.integration import Integration as _Intg
    try:
        result = await db.execute(
            _sel(_Intg).where(
                _Intg.tenant_id == tenant_id,
                _Intg.type      == itype,
                _Intg.is_active == True,
                _Intg.status    == "connected",
            )
        )
        rec = result.scalar_one_or_none()
        if not rec:
            return None
        creds = {}
        for k, v in (rec.credentials or {}).items():
            try:
                from app.utils.encryption import decrypt
                creds[k] = decrypt(v)
            except Exception:
                creds[k] = v
        return {"config": rec.config or {}, "credentials": creds}
    except Exception:
        return None


async def _live_cluster_snapshot(tenant_id: str, db, namespace=None):
    """
    Current cluster utilisation via the tenant K8s integration's metrics-server.

    BUG-012: the previous implementation returned ``cpu_pct = cores * 100`` and
    ``memory_pct = bytes / 1024**2`` (i.e. MiB) under keys the frontend renders
    as percentages. Both were absolute quantities mislabelled as percentages.
    Usage is now divided by real per-node allocatable capacity; when capacity
    is unknown the percentage is reported as null rather than guessed.
    """
    try:
        svc    = KubernetesService(db)
        client = await svc.get_k8s_client_for_tenant(tenant_id)
        if not client:
            return None
        nodes = await client.get_node_metrics()
        if not nodes:
            return None

        capacity = {c["name"]: c for c in await client.get_node_capacity()}

        cpu_used  = cpu_cap = 0.0
        mem_used  = mem_cap = 0.0
        for n in nodes:
            cap = capacity.get(n["name"], {})
            cu, cc = n.get("cpu_usage"),    cap.get("cpu_allocatable")
            mu, mc = n.get("memory_usage"), cap.get("memory_allocatable")
            # Only pair a node's usage with its own capacity, and only when the
            # capacity is a real positive number (guards missing/zero limits).
            if cu is not None and cc and cc > 0:
                cpu_used += cu
                cpu_cap += cc
            if mu is not None and mc and mc > 0:
                mem_used += mu
                mem_cap += mc

        if cpu_cap <= 0 and mem_cap <= 0:
            # metrics-server answered but capacity is unknown — refuse to
            # present absolute cores/MiB as a percentage.
            return None

        return {
            "cpu_pct":    round(cpu_used / cpu_cap * 100, 1) if cpu_cap > 0 else None,
            "memory_pct": round(mem_used / mem_cap * 100, 1) if mem_cap > 0 else None,
        }
    except Exception as exc:
        logger.debug(f"[obs:metrics] live snapshot failed: {exc}")
        return None


async def _resolve_pod_ref(pod_ref: str, tenant_id: str, db) -> Optional[dict]:
    """Accepts DB id or 'namespace/name' and resolves it inside the tenant."""
    from sqlalchemy import select as _sel
    from app.models.pod import Pod as _Pod
    try:
        if "/" in pod_ref:
            ns, name = pod_ref.split("/", 1)
            result = await db.execute(
                _sel(_Pod).where(
                    _Pod.tenant_id == tenant_id,
                    _Pod.name      == name,
                    _Pod.namespace == ns,
                )
            )
        else:
            result = await db.execute(
                _sel(_Pod).where(_Pod.id == pod_ref, _Pod.tenant_id == tenant_id)
            )
        pod = result.scalar_one_or_none()
        if pod:
            return {"name": pod.name, "namespace": pod.namespace or "default"}
    except Exception:
        pass
    return None
