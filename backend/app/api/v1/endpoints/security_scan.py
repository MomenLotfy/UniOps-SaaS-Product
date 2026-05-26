from __future__ import annotations
"""
DevSecOps Scan API
==================
Endpoints:
  GET  /security/repos              — list connected repos
  POST /security/repos/sync         — sync repos from GitHub/GitLab integration
  POST /security/scan               — trigger a new scan (single repo)
  GET  /security/scan/{id}          — poll scan status + results
  POST /security/scan/batch         — scan top N repos in one call
  GET  /security/scan/batch/{id}    — poll batch progress; triggers ML sync on completion
  GET  /security/score              — latest security score (repo-isolated)
  GET  /security/scan-history       — scan timeline (repo-isolated)

Repo Isolation
──────────────
/security/score and /security/scan-history both accept an optional repo_id
query parameter. When supplied, results are strictly scoped to that repository.
When omitted, the aggregate view across all repos is returned.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

# ── In-memory batch tracker ──────────────────────────────────────────────────
# batch_id → { tenant_id, total, scan_ids, scan_meta, ml_synced }
# Safe for single-process dev/prod; replace with Redis for multi-pod deployments.
_BATCHES: dict[str, dict] = {}

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
# Batch scan — scans multiple repos in one call
# ─────────────────────────────────────────────────────────────────────────────

# Language priority: higher = more likely to have exploitable dependencies
_LANG_PRIORITY: dict[str, int] = {
    "typescript": 5, "javascript": 5, "python": 5,
    "go": 4, "java": 4, "ruby": 4,
    "php": 3, "rust": 3, "c": 3, "cpp": 3,
    "hcl": 2, "shell": 2, "dockerfile": 2,
    "html": 1, "hack": 1, "jinja": 1,
    "unknown": 0,
}


@router.post("/scan/batch", status_code=status.HTTP_202_ACCEPTED)
async def trigger_batch_scan(
    current_user: AdminUser,
    tenant_id: TenantID,
    db: DBSession,
    background_tasks: BackgroundTasks,
    max_repos: int = Body(default=5, embed=True, ge=1, le=20),
):
    """
    Trigger security scans across the top N repositories for this tenant.

    Repos are prioritised by language richness (TypeScript/Python > Unknown).
    Already-running repos are skipped. Returns immediately with a batch_id;
    poll GET /security/scan/batch/{batch_id} for progress.
    """
    from sqlalchemy import select as _sel
    from app.models.scan import Repository, Scan

    # ── 1. Load all repos for this tenant ────────────────────────────────────
    result = await db.execute(
        _sel(Repository)
        .where(Repository.tenant_id == tenant_id)
        .order_by(Repository.last_scan_at.asc().nullsfirst())   # prefer un-scanned first
    )
    all_repos = result.scalars().all()

    if not all_repos:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No repositories found. Sync repos first via POST /security/repos/sync.",
        )

    # ── 2. Score + deduplicate by full_name, take top N ───────────────────────
    seen_names: set[str] = set()
    scored: list[tuple[int, Repository]] = []
    for repo in all_repos:
        if repo.full_name in seen_names:
            continue
        seen_names.add(repo.full_name)
        lang    = (repo.language or "unknown").lower()
        priority = _LANG_PRIORITY.get(lang, 0)
        # Bonus for repos with known-vulnerable names
        if any(kw in repo.full_name.lower() for kw in ("juice", "dvwa", "vuln", "hack", "cicd")):
            priority += 3
        scored.append((priority, repo))

    scored.sort(key=lambda x: x[0], reverse=True)
    candidates = [r for _, r in scored[:max_repos * 3]]   # over-fetch to handle skips

    # ── 3. Check for already-running scans (skip those repos) ────────────────
    running_result = await db.execute(
        _sel(Scan.repo_id).where(
            Scan.tenant_id == tenant_id,
            Scan.status.in_(["queued", "cloning", "scanning", "analyzing"]),
        )
    )
    running_repo_ids: set[str] = {r[0] for r in running_result.fetchall()}

    svc = ScanService(db)
    batch_id  = str(uuid.uuid4())
    scan_ids:  list[str] = []
    scan_meta: dict[str, dict] = {}   # scan_id → {repo_name, repo_id, status}
    queued_repos = []

    for repo in candidates:
        if len(scan_ids) >= max_repos:
            break
        if repo.id in running_repo_ids:
            logger.info(f"[batch:{batch_id[:8]}] Skipping {repo.full_name} — already scanning")
            continue
        try:
            scan = await svc.create_scan(
                tenant_id=tenant_id,
                repo_id=repo.id,
                triggered_by=current_user["user_id"],
            )
            scan_ids.append(scan.id)
            scan_meta[scan.id] = {
                "repo_name": repo.full_name,
                "repo_id":   repo.id,
                "status":    "queued",
            }
            queued_repos.append({
                "scan_id":   scan.id,
                "repo_id":   repo.id,
                "repo_name": repo.full_name,
            })
            background_tasks.add_task(svc.dispatch_scan, scan.id)
            logger.info(f"[batch:{batch_id[:8]}] Queued {repo.full_name} → scan {scan.id[:8]}")
        except (ScanAlreadyRunningError, RepoNotFoundError) as exc:
            logger.info(f"[batch:{batch_id[:8]}] Skipped {repo.full_name}: {exc}")

    if not scan_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="All candidate repositories already have active scans. Wait for them to finish.",
        )

    _BATCHES[batch_id] = {
        "tenant_id":  tenant_id,
        "total":      len(scan_ids),
        "scan_ids":   scan_ids,
        "scan_meta":  scan_meta,
        "ml_synced":  False,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        f"[batch:{batch_id[:8]}] Started — "
        f"tenant={tenant_id[:8]} repos={len(scan_ids)}/{len(all_repos)}"
    )
    return APIResponse(
        data={
            "batch_id":   batch_id,
            "total":      len(scan_ids),
            "queued":     queued_repos,
            "skipped":    len(candidates) - len(scan_ids),
        },
        message=f"Batch scan started — scanning {len(scan_ids)} repositories",
    )


@router.get("/scan/batch/{batch_id}")
async def get_batch_scan(
    batch_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    """
    Poll batch scan progress.

    Returns per-repo statuses and overall counts.
    When all scans reach a terminal state (completed/failed) and ml_synced is False,
    automatically triggers an ML insight sync so the vuln forecast is updated.
    """
    import asyncio
    from sqlalchemy import select as _sel
    from app.models.scan import Scan

    batch = _BATCHES.get(batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if batch["tenant_id"] != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # ── Refresh statuses from DB ──────────────────────────────────────────────
    scan_ids = batch["scan_ids"]
    result   = await db.execute(
        _sel(Scan.id, Scan.status, Scan.critical_count, Scan.high_count, Scan.medium_count, Scan.low_count, Scan.security_score)
        .where(Scan.id.in_(scan_ids))
    )
    db_statuses: dict[str, dict] = {
        row[0]: {
            "status":   row[1],
            "critical": row[2] or 0,
            "high":     row[3] or 0,
            "medium":   row[4] or 0,
            "low":      row[5] or 0,
            "score":    row[6],
        }
        for row in result.fetchall()
    }

    # Merge into scan_meta
    for sid in scan_ids:
        if sid in db_statuses:
            batch["scan_meta"][sid].update(db_statuses[sid])

    # ── Aggregate counts ──────────────────────────────────────────────────────
    TERMINAL = {"completed", "failed"}
    statuses  = [batch["scan_meta"][sid]["status"] for sid in scan_ids]
    n_done    = sum(1 for s in statuses if s == "completed")
    n_failed  = sum(1 for s in statuses if s == "failed")
    n_active  = sum(1 for s in statuses if s not in TERMINAL)
    all_done  = all(s in TERMINAL for s in statuses)

    # ── Trigger ML sync once when all scans are terminal ─────────────────────
    if all_done and not batch["ml_synced"]:
        batch["ml_synced"] = True
        logger.info(
            f"[batch:{batch_id[:8]}] All scans done "
            f"(completed={n_done} failed={n_failed}) — triggering ML sync"
        )

        async def _ml_sync():
            try:
                from app.tasks.sync_ml_insights import sync_ml_insights_async
                result = await sync_ml_insights_async(tenant_id=tenant_id)
                logger.info(f"[batch:{batch_id[:8]}] ML sync complete: {result}")
            except Exception as exc:
                logger.warning(f"[batch:{batch_id[:8]}] ML sync failed (non-fatal): {exc!r}")

        asyncio.create_task(_ml_sync(), name=f"batch-ml-sync-{batch_id[:8]}")

    return APIResponse(data={
        "batch_id":   batch_id,
        "total":      batch["total"],
        "completed":  n_done,
        "failed":     n_failed,
        "active":     n_active,
        "all_done":   all_done,
        "ml_synced":  batch["ml_synced"],
        "started_at": batch["started_at"],
        "repos":      [
            {
                "scan_id":   sid,
                "repo_name": batch["scan_meta"][sid]["repo_name"],
                "status":    batch["scan_meta"][sid]["status"],
                "critical":  batch["scan_meta"][sid].get("critical", 0),
                "high":      batch["scan_meta"][sid].get("high", 0),
                "medium":    batch["scan_meta"][sid].get("medium", 0),
                "score":     batch["scan_meta"][sid].get("score"),
            }
            for sid in scan_ids
        ],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Domain exceptions (raised by ScanService, caught here for HTTP mapping)
# ─────────────────────────────────────────────────────────────────────────────

class ScanAlreadyRunningError(Exception):
    """Raised when a concurrent scan is already active for the same repo."""


class RepoNotFoundError(Exception):
    """Raised when the requested repository does not exist for this tenant."""
