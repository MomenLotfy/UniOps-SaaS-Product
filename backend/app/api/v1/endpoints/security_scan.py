from __future__ import annotations
"""
DevSecOps Scan API
==================
Endpoints:
  GET  /security/repos              — list connected repos
  POST /security/repos/sync         — sync repos from GitHub/GitLab integration
  POST /security/scan               — trigger a new scan
  GET  /security/scan/{id}          — poll scan status + results
  GET  /security/score              — latest security score (repo-isolated)
  GET  /security/scan-history       — scan timeline (repo-isolated)

Repo Isolation
──────────────
/security/score and /security/scan-history both accept an optional repo_id
query parameter. When supplied, results are strictly scoped to that repository.
When omitted, the aggregate view across all repos is returned.
"""
from typing import Optional

from fastapi import APIRouter, Query, Body, BackgroundTasks, HTTPException, status

from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.services.integration_service import IntegrationService
from app.services.scan_service import ScanService
from app.utils.logger import logger

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
    logger.info(f"[scan:repos] tenant={tenant_id[:8]} count={len(repos)}")
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
    """
    from sqlalchemy import select as _sel, func as _func
    from app.models.scan import Repository

    svc = IntegrationService(db)
    result = await svc.sync_repos_for_tenant(tenant_id)
    await db.commit()

    existing_count = (await db.execute(
        _sel(_func.count()).select_from(Repository).where(Repository.tenant_id == tenant_id)
    )).scalar() or 0

    logger.info(
        f"[scan:repos/sync] tenant={tenant_id[:8]} "
        f"live_synced={result['synced']} db_total={existing_count}"
    )

    if result["synced"] == 0 and existing_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="integration_not_ready",
        )

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
    background_tasks: BackgroundTasks,
    repo_id: str = Body(..., embed=True),
    branch: Optional[str] = Body(default=None, embed=True),
):
    """
    Trigger a security scan on a repository.
    Returns scan_id immediately; poll GET /security/scan/{id} for results.
    Returns HTTP 409 if a scan is already running for this repo.
    """
    logger.info(
        f"[scan:trigger] repo_id={repo_id[:8]} tenant={tenant_id[:8]} "
        f"branch={branch} user={current_user['user_id'][:8]}"
    )
    svc = ScanService(db)

    try:
        scan = await svc.create_scan(
            tenant_id=tenant_id,
            repo_id=repo_id,
            triggered_by=current_user["user_id"],
            branch=branch,
        )
    except ScanAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    background_tasks.add_task(svc.dispatch_scan, scan.id)

    logger.info(
        f"[scan:trigger] scan_id={scan.id} queued for repo_id={repo_id[:8]}"
    )
    return APIResponse(
        data={
            "scan_id": scan.id,
            "status":  "queued",
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
    repo_id: Optional[str] = Query(
        default=None,
        description="Scope history to a specific repository. Omit for all-repos view.",
    ),
):
    """
    Returns scan history for the Threat Timeline chart.
    Each entry: {date, score, critical, high, medium, low, secrets, repo, repo_id, scan_id}

    ISOLATION: Pass repo_id to see only scans for that repository.
    Omitting repo_id returns the mixed multi-repo history (overview mode).
    """
    logger.info(
        f"[scan:history] tenant={tenant_id[:8]} repo_id={repo_id} limit={limit}"
    )
    svc = ScanService(db)
    timeline = await svc.get_scan_history(tenant_id, limit, repo_id=repo_id)
    return APIResponse(data=timeline)


@router.get("/score")
async def get_security_score(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    repo_id: Optional[str] = Query(
        default=None,
        description="Scope score to a specific repository. Omit for latest scan across all repos.",
    ),
):
    """
    Returns the latest security score for the dashboard.
    Includes: score, breakdown for radar chart, AI summary, repo context.

    ISOLATION: Pass repo_id to get the score for a specific repository only.
    Omitting repo_id returns the most recent scan's score across all repos.
    """
    logger.info(
        f"[scan:score] tenant={tenant_id[:8]} repo_id={repo_id}"
    )
    svc = ScanService(db)
    score_data = await svc.get_latest_score(tenant_id, repo_id=repo_id)
    return APIResponse(data=score_data)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exceptions (raised by ScanService, caught here for HTTP mapping)
# ─────────────────────────────────────────────────────────────────────────────

class ScanAlreadyRunningError(Exception):
    """Raised when a concurrent scan is already active for the same repo."""


class RepoNotFoundError(Exception):
    """Raised when the requested repository does not exist for this tenant."""
