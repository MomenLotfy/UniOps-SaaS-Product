from __future__ import annotations
"""
Logs API — per-pod container logs.

Data sources (real only, in priority order):
  1. Grafana Loki ('loki' integration for the tenant) — history + live tail
  2. Kubernetes API directly (via the tenant's K8s integration) — current
     container logs

NO synthetic logs and NO database audit/deployment logs presented as container
logs.  When neither source is reachable the response returns
``source: "unavailable"`` with an explicit message so the UI can render a
"Not Connected" state.

follow=true returns a Server-Sent Events stream (text/event-stream).  Without
Loki, SSE falls back to Loki-unavailable JSON (not an infinite fake stream).
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.core.exceptions import NotFoundError
from app.models.integration import Integration

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/pods/{pod_id}")
async def get_pod_logs(
    pod_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    request: Request,
    tail: int   = Query(200, ge=1, le=2000, description="Max log lines to return"),
    follow: bool = Query(False, description="Stream logs via SSE (text/event-stream)"),
    filter: str  = Query("", description="Keyword filter"),
    hours: int   = Query(1, ge=1, le=48, description="Look-back window in hours"),
    cluster_id: Optional[str] = Query(None),
):
    pod_name, namespace = await _resolve_pod(pod_id, tenant_id, db)

    loki_client = None
    loki_integration = await _get_integration(db, tenant_id, "loki")
    if loki_integration:
        from app.integrations.observability.loki import get_loki_client
        loki_client = get_loki_client(loki_integration)

    # ── SSE streaming mode ────────────────────────────────────────────────────
    if follow:
        if not loki_client:
            raise HTTPException(
                status_code=503,
                detail="Live log streaming requires a Loki integration — not connected",
            )
        return StreamingResponse(
            _stream_logs(loki_client, pod_id, pod_name, namespace, filter, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Batch mode: Loki first ────────────────────────────────────────────────
    if loki_client:
        try:
            if await loki_client.health():
                logs = await loki_client.query_logs(
                    pod_name, namespace,
                    tail=tail, duration_hours=hours,
                    filter_str=filter,
                )
                return APIResponse(data={
                    "pod_id":    pod_id,
                    "pod_name":  pod_name,
                    "namespace": namespace,
                    "source":    "loki",
                    "tail":      tail,
                    "count":     len(logs),
                    "logs":      logs,
                })
        except Exception as exc:
            logger.warning(f"[logs] Loki fetch failed: {exc}")

    # ── Fall back to direct Kubernetes API log read (real container logs) ─────
    k8s_logs = await _read_k8s_pod_logs(pod_name, namespace, tenant_id, db, tail, filter)
    if k8s_logs is not None:
        return APIResponse(data={
            "pod_id":    pod_id,
            "pod_name":  pod_name,
            "namespace": namespace,
            "source":    "kubernetes",
            "tail":      tail,
            "count":     len(k8s_logs),
            "logs":      k8s_logs,
        })

    # Nothing available — explicit unavailable state, never fake content
    return APIResponse(data={
        "pod_id":    pod_id,
        "pod_name":  pod_name,
        "namespace": namespace,
        "source":    "unavailable",
        "tail":      tail,
        "count":     0,
        "logs":      [],
        "message":   "Logs unavailable — no Loki integration and Kubernetes API not reachable",
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _resolve_pod(pod_id: str, tenant_id: str, db) -> tuple[str, str]:
    """Resolve the pod within the tenant. Supports DB id or 'namespace/name'."""
    from app.models.pod import Pod

    # If caller passed 'namespace/name', resolve by name
    if "/" in pod_id:
        namespace, name = pod_id.split("/", 1)
        result = await db.execute(
            select(Pod).where(
                Pod.tenant_id == tenant_id,
                Pod.name      == name,
                Pod.namespace == namespace,
            )
        )
        pod = result.scalar_one_or_none()
        if not pod:
            raise NotFoundError("Pod", pod_id)
        return pod.name, pod.namespace

    result = await db.execute(
        select(Pod).where(Pod.id == pod_id, Pod.tenant_id == tenant_id)
    )
    pod = result.scalar_one_or_none()
    if pod:
        return pod.name, (pod.namespace or "default")
    raise NotFoundError("Pod", pod_id)


async def _get_integration(db, tenant_id: str, itype: str) -> Optional[dict]:
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
        return {"config": rec.config or {}, "credentials": _decrypt_creds(rec.credentials or {})}
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


async def _read_k8s_pod_logs(
    pod_name: str, namespace: str, tenant_id: str, db,
    tail: int, filter_str: str,
) -> Optional[list[dict]]:
    """Read current container logs via the tenant's K8s integration."""
    try:
        from app.services.kubernetes_service import KubernetesService
        svc    = KubernetesService(db)
        client = await svc.get_k8s_client_for_tenant(tenant_id)
        if not client:
            return None
        k8s = client._get_client()
        if not k8s:
            return None
        v1 = k8s.CoreV1Api()
        raw = v1.read_namespaced_pod_log(
            name=pod_name, namespace=namespace,
            tail_lines=tail, _request_timeout=15,
        ) or ""
    except Exception as exc:
        logger.debug(f"[logs] K8s log read failed: {exc}")
        return None

    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        if filter_str and filter_str.lower() not in line.lower():
            continue
        # Strip ISO timestamp prefix if present
        ts = None
        msg = line
        parts = line.split(" ", 1)
        if parts and parts[0][:4].isdigit() and "T" in parts[0]:
            ts, msg = parts[0], (parts[1] if len(parts) > 1 else "")
        out.append({"timestamp": ts, "level": _detect_level(line), "message": msg})
    return out[-tail:]


def _detect_level(line: str) -> str:
    low = line.lower()
    if any(k in low for k in ("error", "err ", "exception", "fatal", "critical")):
        return "error"
    if any(k in low for k in ("warn", "deprecated")):
        return "warning"
    if any(k in low for k in ("debug", "trace")):
        return "debug"
    return "info"


async def _stream_logs(
    loki_client,
    pod_id: str,
    pod_name: str,
    namespace: str,
    filter_str: str,
    request: Request,
    max_seconds: int = 300,
):
    """
    Async generator for SSE log streaming — REAL data only.

    Format:
      event: connected
      data: {"source": "loki", "pod_id": "..."}

      data: {"timestamp": "...", "level": "...", "message": "..."}
    """
    yield f"event: connected\ndata: {json.dumps({'source': 'loki', 'pod_id': pod_id, 'pod_name': pod_name})}\n\n"

    # Backfill the last 50 lines
    try:
        backfill = await loki_client.query_logs(
            pod_name, namespace, tail=50, duration_hours=1,
            filter_str=filter_str,
        )
        for line in backfill[-50:]:
            yield f"data: {json.dumps(line)}\n\n"
    except Exception as exc:
        logger.warning(f"[logs] Loki backfill failed: {exc}")

    # Live tail — bounded and honouring client disconnect
    started = asyncio.get_event_loop().time()
    try:
        async for line in loki_client.tail_logs(pod_name, namespace, filter_str=filter_str):
            if await request.is_disconnected():
                return
            if asyncio.get_event_loop().time() - started > max_seconds:
                yield f"event: closed\ndata: {json.dumps({'reason': 'stream_time_limit'})}\n\n"
                return
            yield f"data: {json.dumps(line)}\n\n"
    except Exception as exc:
        logger.warning(f"[logs] Loki tail error: {exc}")
        yield f"event: error\ndata: {json.dumps({'message': 'log stream interrupted'})}\n\n"
