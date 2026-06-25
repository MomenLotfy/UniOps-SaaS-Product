from __future__ import annotations
"""
Kubernetes Security API
=======================
GET  /k8s/clusters                              — list clusters with risk scores
GET  /k8s/clusters/{cluster_id}/scan-history
POST /k8s/clusters/{cluster_id}/scan            — trigger scan (fire-and-forget)
WS   /k8s/clusters/{cluster_id}/scan-stream     — streaming scan over WebSocket
GET  /k8s/findings                              — list findings (filterable)
GET  /k8s/findings/stats                        — severity/category summary
PATCH /k8s/findings/{finding_id}/suppress
PATCH /k8s/findings/{finding_id}/resolve
GET  /k8s/scans/{scan_id}                       — single scan details
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, WebSocket, WebSocketDisconnect, status as http_status

from app.api.deps import CurrentUser, TenantID, DBSession
from app.core.security import decode_token
from app.core.database import AsyncSessionLocal
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


@router.websocket("/clusters/{cluster_id}/scan-stream")
async def scan_stream(
    websocket: WebSocket,
    cluster_id: str,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint that streams scan progress in real-time.
    Auth via ?token=<jwt> (browsers cannot set Authorization header on WS).

    Message types emitted (JSON):
      {"type": "auth_ok",    "tenant_id": "..."}
      {"type": "scan_start", "scan_id": "...", "cluster": "..."}
      {"type": "phase_start","phase": "...", "label": "..."}
      {"type": "phase_done", "phase": "...", "count": N, "findings": [...]}
      {"type": "scanner",    "scanner": "kubescape|kube-bench|kube-hunter", "status": "running|done|skipped", "count": N}
      {"type": "complete",   "scan_id": "...", "total": N, "risk_score": N}
      {"type": "error",      "message": "..."}
    """
    await websocket.accept()

    # ── Auth ──────────────────────────────────────────────────────────────────
    if not token:
        await websocket.send_text(json.dumps({"type": "error", "message": "token required"}))
        await websocket.close(code=4001)
        return

    try:
        payload = decode_token(token)
        tenant_id: str = payload.get("tenant_id", "")
        user_id: str   = payload.get("sub", "")
        if not tenant_id or not user_id:
            raise ValueError("missing claims")
    except Exception:
        await websocket.send_text(json.dumps({"type": "error", "message": "invalid token"}))
        await websocket.close(code=4001)
        return

    await websocket.send_text(json.dumps({"type": "auth_ok", "tenant_id": tenant_id}))

    # ── asyncio queue bridges sync scanner → async WS sender ─────────────────
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def emit(event: dict) -> None:
        """Called from a thread executor — schedules a queue put on the event loop."""
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def ws_sender():
        """Drain the queue and forward events to the WebSocket client."""
        while True:
            event = await queue.get()
            if event is None:   # sentinel — scanner done
                break
            try:
                await websocket.send_text(json.dumps(event, default=str))
            except Exception:
                break

    # ── Run scan in thread executor (blocking kubernetes client calls) ─────────
    async with AsyncSessionLocal() as db:
        svc = K8sSecurityService(db)
        try:
            scan, cluster = await svc.create_scan_record(tenant_id, cluster_id)
        except ValueError as e:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
            await websocket.close(code=4004)
            return

        await websocket.send_text(json.dumps({
            "type": "scan_start",
            "scan_id": scan.id,
            "cluster": cluster.name,
        }))

        sender_task = asyncio.create_task(ws_sender())

        try:
            # Run the streaming native scan in a thread (it does blocking k8s calls)
            from app.services.k8s_security_service import NativeK8sScanner, _run_kubescape, _run_kube_bench, _run_kube_hunter, _serialize_finding
            native = NativeK8sScanner(cluster)

            native_findings = await loop.run_in_executor(
                None, lambda: native.scan_streaming(emit)
            )

            scanners_run = ["native"] if native_findings is not None else []
            all_findings = list(native_findings or [])

            # External scanners
            kubeconfig = cluster.kubeconfig_encrypted
            if kubeconfig:
                import tempfile, os
                tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
                try:
                    tmp.write(kubeconfig)
                    tmp.flush()
                    kc_path = tmp.name

                    for scanner_name, runner in [
                        ("kubescape", lambda: _run_kubescape(kc_path)),
                        ("kube-bench", lambda: _run_kube_bench(kc_path)),
                    ]:
                        emit({"type": "scanner", "scanner": scanner_name, "status": "running"})
                        results = await runner()
                        if results:
                            all_findings += results
                            scanners_run.append(scanner_name)
                            emit({"type": "scanner", "scanner": scanner_name, "status": "done", "count": len(results),
                                  "findings": [_serialize_finding(f) for f in results]})
                        else:
                            emit({"type": "scanner", "scanner": scanner_name, "status": "skipped", "count": 0})
                finally:
                    tmp.close()
                    try: os.unlink(tmp.name)
                    except Exception: pass

            if cluster.api_server_url:
                emit({"type": "scanner", "scanner": "kube-hunter", "status": "running"})
                kh = await _run_kube_hunter(cluster.api_server_url)
                if kh:
                    all_findings += kh
                    scanners_run.append("kube-hunter")
                    emit({"type": "scanner", "scanner": "kube-hunter", "status": "done", "count": len(kh),
                          "findings": [_serialize_finding(f) for f in kh]})
                else:
                    emit({"type": "scanner", "scanner": "kube-hunter", "status": "skipped", "count": 0})

            # Persist findings
            await svc.persist_findings(db, tenant_id, cluster, scan.id, all_findings, scanners_run)

            risk = svc.compute_risk_score(all_findings)
            emit({
                "type": "complete",
                "scan_id": scan.id,
                "total": len(all_findings),
                "risk_score": risk,
            })

        except WebSocketDisconnect:
            logger.info(f"[k8s_security_ws] Client disconnected mid-scan for cluster {cluster_id}")
        except Exception as exc:
            logger.error(f"[k8s_security_ws] Scan stream error: {exc}")
            emit({"type": "error", "message": str(exc)})
        finally:
            emit(None)  # sentinel — stop sender
            await sender_task
            try:
                await websocket.close()
            except Exception:
                pass

    logger.info(f"[k8s_security_ws] Stream session ended for cluster {cluster_id} user {user_id}")


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
