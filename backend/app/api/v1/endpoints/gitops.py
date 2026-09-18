from __future__ import annotations
"""
GitOps API — ArgoCD-style application management (Epic 5).
Manages a local registry of GitOps apps with ArgoCD proxy support
when an ArgoCD server URL + token are stored in the integration.
"""
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Depends
from app.core.rate_limit import rate_limit
from app.api.deps import DevOpsUser
from pydantic import BaseModel as PydanticModel
from sqlalchemy import select
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.models.gitops_app import GitOpsApp
from app.models.gitops_history import GitOpsHistory
from app.models.integration import Integration

router = APIRouter()
logger = logging.getLogger(__name__)

HEALTH_STATUSES = ["Healthy", "Degraded", "Progressing", "Missing", "Suspended", "Unknown"]
SYNC_STATUSES   = ["Synced", "OutOfSync", "Unknown"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _app_dict(a: GitOpsApp) -> dict:
    return {
        "id":              a.id,
        "name":            a.name,
        "project":         a.project,
        "namespace":       a.namespace,
        "cluster_id":      a.cluster_id,
        "cluster_server":  a.cluster_server,
        "source_type":     a.source_type,
        "repo_url":        a.repo_url,
        "target_revision": a.target_revision,
        "path":            a.path,
        "helm_chart":      a.helm_chart,
        "health_status":   a.health_status,
        "sync_status":     a.sync_status,
        "sync_message":    a.sync_message,
        "last_synced_at":  a.last_synced_at.isoformat() if a.last_synced_at else None,
        "current_revision":a.current_revision,
        "argocd_app_name": a.argocd_app_name,
        "argocd_server":   a.argocd_server,
        "resource_summary":a.resource_summary,
        "created_at":      a.created_at.isoformat(),
    }


def _hist_dict(h: GitOpsHistory) -> dict:
    return {
        "id":          h.id,
        "app_id":      h.app_id,
        "revision":    h.revision,
        "short_sha":   h.short_sha,
        "author":      h.author,
        "message":     h.message,
        "deployed_at": h.deployed_at.isoformat(),
        "deployed_by": h.deployed_by,
        "status":      h.status,
        "source_type": h.source_type,
    }


async def _get_argocd_creds(tenant_id: str, db: DBSession) -> dict | None:
    """Return ArgoCD server + token from integrations, or None."""
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id,
            Integration.type      == "argocd",
            Integration.is_active == True,
            Integration.status    == "connected",
        ).limit(1)
    )
    integ = result.scalar_one_or_none()
    if not integ:
        return None
    from app.utils.encryption import decrypt
    creds = {}
    for k, v in (integ.credentials or {}).items():
        try:
            creds[k] = decrypt(v)
        except Exception:
            creds[k] = v
    cfg = integ.config or {}
    # Accept server_url/token from config or credentials (both are used in practice)
    return {
        "server":   creds.get("server_url") or cfg.get("server_url") or cfg.get("url", ""),
        "token":    creds.get("token") or creds.get("argocd_token") or "",
        "insecure": (creds.get("insecure") or cfg.get("insecure") or False),
    }


async def _argocd_list_apps(creds: dict) -> list[dict]:
    """Call ArgoCD /api/v1/applications."""
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            r = await client.get(
                f"{creds['server'].rstrip('/')}/api/v1/applications",
                headers={"Authorization": f"Bearer {creds['token']}"},
            )
            r.raise_for_status()
            return r.json().get("items", [])
    except Exception as e:
        logger.warning(f"[gitops] ArgoCD list_apps failed: {e}")
        return []


async def _argocd_sync(creds: dict, app_name: str) -> bool:
    try:
        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            r = await client.post(
                f"{creds['server'].rstrip('/')}/api/v1/applications/{app_name}/sync",
                headers={"Authorization": f"Bearer {creds['token']}"},
                json={},
            )
            return r.status_code < 300
    except Exception as e:
        logger.warning(f"[gitops] ArgoCD sync failed: {e}")
        return False


async def _argocd_rollback(creds: dict, app_name: str, revision: str) -> bool:
    try:
        # ArgoCD's /rollback API expects the integer history "id" of the
        # deployment revision.  When we don't know it we fetch history first.
        id_number: int | str = revision
        try:
            id_number = int(revision)
        except (TypeError, ValueError):
            # Revision is a SHA — resolve it through ArgoCD history
            hist = await _argocd_get_history(creds, app_name)
            match = next((h for h in hist if (h.get("revision") or "").startswith(revision[:7])), None)
            if match is None or "id" not in match:
                return False
            id_number = match["id"]

        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            r = await client.post(
                f"{creds['server'].rstrip('/')}/api/v1/applications/{app_name}/rollback",
                headers={"Authorization": f"Bearer {creds['token']}"},
                json={"id": id_number},
            )
            return r.status_code < 300
    except Exception as e:
        logger.warning(f"[gitops] ArgoCD rollback failed: {e}")
        return False


async def _argocd_get_history(creds: dict, app_name: str) -> list[dict]:
    """Fetch deployment history from ArgoCD (revision + id entries)."""
    try:
        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            r = await client.get(
                f"{creds['server'].rstrip('/')}/api/v1/applications/{app_name}",
                headers={"Authorization": f"Bearer {creds['token']}"},
            )
            if r.status_code != 200:
                return []
            return (r.json().get("status") or {}).get("history", []) or []
    except Exception as e:
        logger.warning(f"[gitops] ArgoCD history fetch failed: {e}")
        return []


async def _argocd_get_revision(creds: dict, app_name: str) -> str | None:
    """Current live sync revision in ArgoCD, or None when unreachable."""
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            r = await client.get(
                f"{creds['server'].rstrip('/')}/api/v1/applications/{app_name}",
                headers={"Authorization": f"Bearer {creds['token']}"},
            )
            if r.status_code != 200:
                return None
            return ((r.json().get("status") or {}).get("sync") or {}).get("revision")
    except Exception as e:
        logger.warning(f"[gitops] ArgoCD revision fetch failed: {e}")
        return None


# ── Schemas ───────────────────────────────────────────────────────────────────

class AppCreate(PydanticModel):
    name:            str
    project:         str = "default"
    namespace:       str = "default"
    cluster_id:      Optional[str] = None
    source_type:     str = "git"
    repo_url:        Optional[str] = None
    target_revision: str = "HEAD"
    path:            Optional[str] = None
    helm_chart:      Optional[str] = None
    argocd_app_name: Optional[str] = None


class AppUpdate(PydanticModel):
    health_status:    Optional[str] = None
    sync_status:      Optional[str] = None
    current_revision: Optional[str] = None
    sync_message:     Optional[str] = None


class SyncRequest(PydanticModel):
    hard_sync: bool = False
    dry_run:   bool = False


class RollbackRequest(PydanticModel):
    revision: str
    message:  Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_apps(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    cluster_id:    Optional[str] = Query(None),
    health_status: Optional[str] = Query(None),
    sync_status:   Optional[str] = Query(None),
):
    q = select(GitOpsApp).where(GitOpsApp.tenant_id == tenant_id)
    if cluster_id:    q = q.where(GitOpsApp.cluster_id    == cluster_id)
    if health_status: q = q.where(GitOpsApp.health_status == health_status)
    if sync_status:   q = q.where(GitOpsApp.sync_status   == sync_status)
    q = q.order_by(GitOpsApp.created_at.desc())
    result = await db.execute(q)
    apps = result.scalars().all()

    # Try ArgoCD live sync if connected
    creds = await _get_argocd_creds(tenant_id, db)
    argocd_map: dict[str, dict] = {}
    if creds:
        live_apps = await _argocd_list_apps(creds)
        for la in live_apps:
            meta = la.get("metadata", {})
            status = la.get("status", {})
            argocd_map[meta.get("name", "")] = {
                "health_status":    status.get("health", {}).get("status", "Unknown"),
                "sync_status":      status.get("sync", {}).get("status", "Unknown"),
                "current_revision": status.get("sync", {}).get("revision", ""),
            }

    result_list = []
    for a in apps:
        d = _app_dict(a)
        # Overlay live ArgoCD data if matched
        if a.argocd_app_name and a.argocd_app_name in argocd_map:
            live = argocd_map[a.argocd_app_name]
            d["health_status"]    = live["health_status"]
            d["sync_status"]      = live["sync_status"]
            d["current_revision"] = live["current_revision"]
        result_list.append(d)

    return APIResponse(data=result_list, message=f"argocd={'connected' if creds else 'disconnected'}")


@router.post(
    "", status_code=201,
    dependencies=[Depends(rate_limit("gitops.create", 10, 60))],
)
async def create_app(
    body: AppCreate,
    current_user: DevOpsUser, tenant_id: TenantID, db: DBSession,
):
    app = GitOpsApp(
        tenant_id=tenant_id,
        name=body.name,
        project=body.project,
        namespace=body.namespace,
        cluster_id=body.cluster_id,
        source_type=body.source_type,
        repo_url=body.repo_url,
        target_revision=body.target_revision,
        path=body.path,
        helm_chart=body.helm_chart,
        argocd_app_name=body.argocd_app_name or body.name,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return APIResponse(data=_app_dict(app), message="App registered")


@router.get("/{app_id}")
async def get_app(
    app_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    result = await db.execute(
        select(GitOpsApp).where(GitOpsApp.id == app_id, GitOpsApp.tenant_id == tenant_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return APIResponse(data=_app_dict(app))


@router.patch("/{app_id}")
async def update_app_status(
    app_id: str, body: AppUpdate,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    result = await db.execute(
        select(GitOpsApp).where(GitOpsApp.id == app_id, GitOpsApp.tenant_id == tenant_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if body.health_status:    app.health_status    = body.health_status
    if body.sync_status:      app.sync_status      = body.sync_status
    if body.current_revision: app.current_revision = body.current_revision
    if body.sync_message:     app.sync_message     = body.sync_message
    await db.commit()
    return APIResponse(data=_app_dict(app))


@router.post(
    "/{app_id}/sync",
    dependencies=[Depends(rate_limit("gitops.sync", 20, 60))],
)
async def sync_app(
    app_id: str, body: SyncRequest,
    current_user: DevOpsUser, tenant_id: TenantID, db: DBSession,
):
    result = await db.execute(
        select(GitOpsApp).where(GitOpsApp.id == app_id, GitOpsApp.tenant_id == tenant_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    creds = await _get_argocd_creds(tenant_id, db)
    if not creds or not creds.get("server") or not creds.get("token"):
        raise HTTPException(
            status_code=503,
            detail="ArgoCD not connected — sync requires an ArgoCD integration",
        )
    if not app.argocd_app_name:
        raise HTTPException(
            status_code=409,
            detail="This application is not registered with ArgoCD",
        )

    # REALLY trigger the sync in ArgoCD — only mark local state on success
    argocd_ok = await _argocd_sync(creds, app.argocd_app_name)
    if not argocd_ok:
        raise HTTPException(
            status_code=502,
            detail=f"ArgoCD sync call failed for application '{app.argocd_app_name}'",
        )

    if not body.dry_run:
        app.last_synced_at = datetime.now(timezone.utc)
        app.sync_message = "Sync triggered via ArgoCD"

    # History records the TRIGGGER as Running — completion is reconciled by
    # the background ArgoCD poller, not assumed synchronously.
    hist = GitOpsHistory(
        tenant_id=tenant_id,
        app_id=app.id,
        revision=app.current_revision or "HEAD",
        short_sha=(app.current_revision or "")[:7] or "—",
        author=(current_user.get("email") or "system") if isinstance(current_user, dict) else getattr(current_user, "email", "system"),
        message="Manual sync" + (" (dry-run)" if body.dry_run else ""),
        deployed_at=datetime.now(timezone.utc),
        deployed_by=(current_user.get("email") or "system") if isinstance(current_user, dict) else getattr(current_user, "email", "system"),
        status="Running" if not body.dry_run else "Succeeded",
        source_type="sync",
    )
    db.add(hist)
    await db.commit()

    return APIResponse(data=_app_dict(app), message="Sync triggered via ArgoCD")


@router.post(
    "/{app_id}/rollback",
    dependencies=[Depends(rate_limit("gitops.rollback", 10, 60))],
)
async def rollback_app(
    app_id: str, body: RollbackRequest,
    current_user: DevOpsUser, tenant_id: TenantID, db: DBSession,
):
    result = await db.execute(
        select(GitOpsApp).where(GitOpsApp.id == app_id, GitOpsApp.tenant_id == tenant_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    creds = await _get_argocd_creds(tenant_id, db)
    if not creds or not creds.get("server") or not creds.get("token"):
        raise HTTPException(
            status_code=503,
            detail="ArgoCD not connected — rollback requires an ArgoCD integration",
        )
    if not app.argocd_app_name:
        raise HTTPException(
            status_code=409,
            detail="This application is not registered with ArgoCD",
        )

    # REALLY execute the rollback in ArgoCD, then verify against the
    # revision actually deployed — never report success unconditionally.
    ok = await _argocd_rollback(creds, app.argocd_app_name, body.revision)
    if not ok:
        raise HTTPException(
            status_code=502,
            detail=f"ArgoCD rollback call failed for application '{app.argocd_app_name}'",
        )

    # Verify the effective revision in ArgoCD after the call
    live = await _argocd_get_revision(creds, app.argocd_app_name)
    if live:
        app.current_revision = live
        app.sync_status      = "Synced"
        app.last_synced_at   = datetime.now(timezone.utc)
    else:
        # Rollback accepted but live revision can't be confirmed yet —
        # mark Progressing so the UI doesn't claim success prematurely.
        app.health_status = "Progressing"
        app.sync_status   = "OutOfSync"
        app.sync_message  = "Rollback accepted — verifying in ArgoCD"
        app.last_synced_at = datetime.now(timezone.utc)

    live_rev = app.current_revision or body.revision
    hist = GitOpsHistory(
        tenant_id=tenant_id,
        app_id=app.id,
        revision=live_rev,
        short_sha=live_rev[:7] if live_rev else "—",
        author=(current_user.get("email") or "system") if isinstance(current_user, dict) else getattr(current_user, "email", "system"),
        message=body.message or f"Rollback to {body.revision[:7]}",
        deployed_at=datetime.now(timezone.utc),
        deployed_by=(current_user.get("email") or "system") if isinstance(current_user, dict) else getattr(current_user, "email", "system"),
        status="Running" if not live else "Succeeded",
        source_type="rollback",
    )
    db.add(hist)
    await db.commit()

    return APIResponse(
        data=_app_dict(app),
        message=(
            f"Rollback to {live_rev[:7]} applied in ArgoCD"
            if live else
            "Rollback accepted by ArgoCD — status will reconcile shortly"
        ),
    )


@router.get("/{app_id}/history")
async def get_app_history(
    app_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    limit: int = Query(20, ge=1, le=100),
):
    result = await db.execute(
        select(GitOpsApp).where(GitOpsApp.id == app_id, GitOpsApp.tenant_id == tenant_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    h_result = await db.execute(
        select(GitOpsHistory)
        .where(GitOpsHistory.app_id == app_id, GitOpsHistory.tenant_id == tenant_id)
        .order_by(GitOpsHistory.deployed_at.desc())
        .limit(limit)
    )
    history = h_result.scalars().all()
    return APIResponse(data=[_hist_dict(h) for h in history])


@router.delete(
    "/{app_id}", status_code=204,
    dependencies=[Depends(rate_limit("gitops.delete", 10, 60))],
)
async def delete_app(
    app_id: str,
    current_user: DevOpsUser, tenant_id: TenantID, db: DBSession,
):
    result = await db.execute(
        select(GitOpsApp).where(GitOpsApp.id == app_id, GitOpsApp.tenant_id == tenant_id)
    )
    app = result.scalar_one_or_none()
    if app:
        await db.delete(app)
        await db.commit()


@router.get("/stats/summary")
async def get_stats(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    result = await db.execute(select(GitOpsApp).where(GitOpsApp.tenant_id == tenant_id))
    apps = result.scalars().all()
    by_health = {}
    by_sync   = {}
    for a in apps:
        by_health[a.health_status] = by_health.get(a.health_status, 0) + 1
        by_sync[a.sync_status]     = by_sync.get(a.sync_status, 0) + 1
    creds = await _get_argocd_creds(tenant_id, db)
    return APIResponse(data={
        "total":       len(apps),
        "healthy":     by_health.get("Healthy", 0),
        "degraded":    by_health.get("Degraded", 0),
        "progressing": by_health.get("Progressing", 0),
        "synced":      by_sync.get("Synced", 0),
        "out_of_sync": by_sync.get("OutOfSync", 0),
        "argocd_connected": bool(creds),
    })


# ── Epic 9 — Real ArgoCD Status Endpoint ─────────────────────────────────────

@router.get("/applications/{app_id}/status")
async def get_application_status(
    app_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    refresh: bool = False,
):
    """
    Real-time ArgoCD application status (Epic 9 — Module 3).

    Response shape:
      {
        "sync_status":   "Synced | OutOfSync | Unknown",
        "health_status": "Healthy | Progressing | Failed | Unknown",
        "diff":          {...},
        "resources":     [...],
        "revision":      "abc123",
        "last_synced_at": "ISO-8601",
        "source":        "argocd | db"
      }

    Data source priority:
      1. Live ArgoCD API (when argocd integration is configured)
      2. Local GitOpsApp record in DB
    """
    result = await db.execute(
        select(GitOpsApp).where(
            GitOpsApp.id        == app_id,
            GitOpsApp.tenant_id == tenant_id,
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    argocd_name = app.argocd_app_name or app.name

    # ── Try live ArgoCD ───────────────────────────────────────────────────────
    creds = await _get_argocd_creds(tenant_id, db)
    if creds and creds.get("server") and creds.get("token"):
        from app.integrations.gitops.argocd_client import ArgoCDSyncClient
        client = ArgoCDSyncClient(
            server_url=creds["server"],
            token=creds["token"],
            insecure=True,
        )

        try:
            if refresh:
                await client.refresh_application(argocd_name)

            status = await client.get_application_status(argocd_name)
            diff   = await client.get_app_diff(argocd_name)

            # Keep DB record in sync
            if status["sync_status"] != "Unknown":
                app.sync_status   = status["sync_status"]
                app.health_status = status["health_status"]
                if status.get("revision"):
                    app.current_revision = status["revision"]
                await db.commit()

                # Emit event to event bus
                try:
                    from app.core.events.event_bus import event_bus
                    await event_bus.emit(
                        f"gitops.{'synced' if status['sync_status'] == 'Synced' else 'out_of_sync'}",
                        {
                            "app_id":      app_id,
                            "app_name":    argocd_name,
                            "sync_status": status["sync_status"],
                            "health":      status["health_status"],
                        },
                        tenant_id=tenant_id,
                    )
                except Exception:
                    pass

            return APIResponse(data={
                **status,
                "diff":   diff,
                "source": "argocd",
            })

        except Exception as exc:
            logger.warning(f"[gitops] ArgoCD status fetch failed for {argocd_name}: {exc}")

    # ── Fallback: DB record ───────────────────────────────────────────────────
    return APIResponse(data={
        "app_name":      app.name,
        "sync_status":   app.sync_status   or "Unknown",
        "health_status": app.health_status or "Unknown",
        "revision":      app.current_revision or "",
        "last_synced_at": app.last_synced_at.isoformat() if app.last_synced_at else None,
        "resources":     (app.resource_summary or {}).get("resources", []),
        "diff":          {},
        "message":       "ArgoCD not connected — showing cached state",
        "source":        "db",
    })


@router.post(
    "/applications/{app_id}/sync",
    dependencies=[Depends(rate_limit("gitops.sync", 20, 60))],
)
async def sync_application_v2(
    app_id: str,
    current_user: DevOpsUser, tenant_id: TenantID, db: DBSession,
    revision: str = "HEAD",
    prune: bool = False,
):
    """
    Trigger a real ArgoCD sync (Epic 9).
    Falls back to updating local record only if ArgoCD is not configured.
    """
    result = await db.execute(
        select(GitOpsApp).where(
            GitOpsApp.id == app_id, GitOpsApp.tenant_id == tenant_id
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    creds = await _get_argocd_creds(tenant_id, db)
    if not creds or not creds.get("server") or not creds.get("token"):
        raise HTTPException(
            status_code=503,
            detail="ArgoCD not connected — sync requires an ArgoCD integration",
        )

    from app.integrations.gitops.argocd_client import ArgoCDSyncClient
    client = ArgoCDSyncClient(creds["server"], creds["token"], insecure=creds.get("insecure", True))
    argocd_name = app.argocd_app_name or app.name
    try:
        synced_live = await client.sync_application(argocd_name, revision=revision, prune=prune)
    except Exception as exc:
        logger.warning(f"[gitops] ArgoCD sync failed: {exc}")
        synced_live = False

    if not synced_live:
        raise HTTPException(
            status_code=502,
            detail=f"ArgoCD sync call failed for application '{argocd_name}'",
        )

    from datetime import datetime, timezone
    app.last_synced_at = datetime.now(timezone.utc)
    app.sync_message = "Sync triggered via ArgoCD"
    await db.commit()

    return APIResponse(data={
        "app_id":     app_id,
        "synced":     True,
        "source":     "argocd",
        "message":    "Sync triggered in ArgoCD",
    })


@router.post(
    "/applications/{app_id}/rollback",
    dependencies=[Depends(rate_limit("gitops.rollback", 10, 60))],
)
async def rollback_application(
    app_id: str,
    current_user: DevOpsUser, tenant_id: TenantID, db: DBSession,
    revision_id: int = 0,
):
    """
    Roll back an ArgoCD application to a prior revision (Epic 9).
    """
    result = await db.execute(
        select(GitOpsApp).where(
            GitOpsApp.id == app_id, GitOpsApp.tenant_id == tenant_id
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    creds = await _get_argocd_creds(tenant_id, db)
    if not creds or not creds.get("server") or not creds.get("token"):
        raise HTTPException(
            status_code=503,
            detail="ArgoCD not connected — rollback requires an ArgoCD integration",
        )

    from app.integrations.gitops.argocd_client import ArgoCDSyncClient
    client      = ArgoCDSyncClient(creds["server"], creds["token"], insecure=creds.get("insecure", True))
    argocd_name = app.argocd_app_name or app.name
    try:
        rolled_back = await client.rollback_application(argocd_name, revision_id)
    except Exception as exc:
        logger.warning(f"[gitops] Rollback failed: {exc}")
        rolled_back = False

    if not rolled_back:
        raise HTTPException(
            status_code=502,
            detail=f"ArgoCD rollback call failed for application '{argocd_name}'",
        )

    from datetime import datetime, timezone
    app.health_status = "Progressing"
    app.sync_status   = "OutOfSync"
    app.sync_message  = f"Rollback to revision id {revision_id} accepted — verifying"
    app.last_synced_at = datetime.now(timezone.utc)
    await db.commit()

    return APIResponse(data={
        "app_id":      app_id,
        "rolled_back": True,
        "revision_id": revision_id,
        "source":      "argocd",
    })
