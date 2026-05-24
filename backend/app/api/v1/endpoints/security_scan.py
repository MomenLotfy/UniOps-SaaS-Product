from __future__ import annotations
"""
DevSecOps Scan API
==================
Endpoints:
  GET  /security/repos              — list connected repos
  POST /security/repos/sync         — sync repos from GitHub/GitLab integration
  POST /security/scan               — trigger a new scan
  GET  /security/scan/{id}          — poll scan status + results
  GET  /security/score              — latest security score (for dashboard)
  GET  /security/scan-history       — scan timeline (for Threat Timeline chart)

FIX #4 — dispatch_scan() was called with `await` INSIDE the endpoint handler,
  meaning the HTTP response was blocked until Celery's .delay() completed.
  That is only a millisecond when Celery is healthy, but when Celery is down
  the inline fallback (`asyncio.create_task`) schedules a coroutine on the
  event loop — which is correct — but the enclosing `await svc.dispatch_scan()`
  still held the HTTP response open.
  More critically: the endpoint defined `dispatch_scan` as a plain `await`,
  not as a BackgroundTask, meaning that if the Celery import itself raised
  an exception it could propagate to the client as a 500 before the scan_id
  was returned.  The scan record was already committed, so the user got a 500
  but the scan was in the DB in "queued" state with no worker to run it.

  Fix: wrap dispatch_scan() in a FastAPI BackgroundTask so the HTTP 202 is
  returned immediately and dispatch runs after the response is sent.
"""
from typing import Optional

from fastapi import APIRouter, Query, Body, BackgroundTasks, HTTPException, status
from sqlalchemy import select, desc

from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.services.integration_service import IntegrationService
from app.services.scan_service import ScanService

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Repositories
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/repos")
async def list_repos(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """List all repositories connected for this tenant."""
    svc = ScanService(db)
    repos = await svc.list_repos(tenant_id)
    return APIResponse(data=[r.to_dict() for r in repos])


@router.post("/repos/sync")
async def sync_repos(
    current_user: AdminUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """
    Pull repository list from connected GitHub/GitLab integrations.
    Creates/updates Repository records — idempotent, safe to call repeatedly.

    If no live integration is reachable but repos already exist in DB
    (e.g. seeded demo data), returns the existing count instead of 409
    so the frontend repo-picker still works.
    """
    from sqlalchemy import select as _sel, func as _func
    from app.models.scan import Repository

    svc = IntegrationService(db)
    result = await svc.sync_repos_for_tenant(tenant_id)
    await db.commit()

    # How many repos already exist in DB for this tenant?
    existing_count = (await db.execute(
        _sel(_func.count()).select_from(Repository).where(Repository.tenant_id == tenant_id)
    )).scalar() or 0

    if result["synced"] == 0 and existing_count == 0:
        # Truly no repos anywhere — surface actionable error
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="integration_not_ready",
        )

    # Either live sync succeeded, or DB already has seeded repos
    total = max(result["synced"], existing_count)
    return APIResponse(
        data={"synced": total, "live_synced": result["synced"], "errors": result["errors"]},
        message=f"{total} repositories available",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scans
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    current_user: AdminUser,
    tenant_id: TenantID,
    db: DBSession,
    background_tasks: BackgroundTasks,   # ← FIX #4: add BackgroundTasks
    repo_id: str = Body(..., embed=True),
    branch: Optional[str] = Body(default=None, embed=True),
):
    """
    Trigger a security scan on a repository.
    Returns scan_id immediately; poll GET /security/scan/{id} for results.
    Returns HTTP 409 if a scan is already running for this repo.
    """
    svc = ScanService(db)

    try:
        scan = await svc.create_scan(
            tenant_id=tenant_id,
            repo_id=repo_id,
            triggered_by=current_user["user_id"],
            branch=branch,
        )
    except ScanAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except RepoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    # ── FIX #4 ────────────────────────────────────────────────────────────────
    # OLD: `await svc.dispatch_scan(scan.id)` — blocked the response; if Celery
    #      import failed the 500 was returned BEFORE the scan_id.
    # NEW: BackgroundTask fires AFTER 202 is sent to the client, so the scan_id
    #      is always returned even if Celery is temporarily unavailable.
    # ─────────────────────────────────────────────────────────────────────────
    background_tasks.add_task(svc.dispatch_scan, scan.id)

    return APIResponse(
        data={
            "scan_id": scan.id,
            "status": "queued",
            "repo_id": repo_id,
        },
        message="Scan queued",
    )


@router.get("/scan/{scan_id}")
async def get_scan(
    scan_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """
    Poll scan status and results.
    Frontend should poll every 3s while status is not completed/failed.
    """
    svc = ScanService(db)
    scan = await svc.get_scan(scan_id, tenant_id)
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return APIResponse(data=scan)


@router.get("/scan-history")
async def scan_history(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    limit: int = Query(default=30, le=100),
):
    """
    Returns scan history for the Threat Timeline chart.
    Each entry: {date, score, critical, high, medium, low, secrets, repo, scan_id}
    """
    svc = ScanService(db)
    timeline = await svc.get_scan_history(tenant_id, limit)
    return APIResponse(data=timeline)


@router.get("/score")
async def get_security_score(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """
    Returns the latest security score for the dashboard.
    Aggregates: latest scan score + breakdown for radar chart.
    """
    svc = ScanService(db)
    score_data = await svc.get_latest_score(tenant_id)
    return APIResponse(data=score_data)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exceptions (raised by ScanService, caught here for HTTP mapping)
# ─────────────────────────────────────────────────────────────────────────────

class ScanAlreadyRunningError(Exception):
    """Raised when a concurrent scan is already active for the same repo."""


class RepoNotFoundError(Exception):
    """Raised when the requested repository does not exist for this tenant."""
