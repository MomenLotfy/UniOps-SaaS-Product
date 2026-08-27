from __future__ import annotations
"""
ScanService
===========
Owns all business logic for the DevSecOps scan subsystem:
  - Repository listing
  - Scan creation (with concurrency guard)
  - Scan dispatch (Celery → async fallback)
  - Scan status reads
  - Scan history + score (repo-isolated)

Concurrency guard
─────────────────
When multiple API pods receive simultaneous POST /security/scan for the same
repo_id, the old code had a TOCTOU window:

  Pod A: SELECT ... WHERE status IN ('queued',...)  → no row found
  Pod B: SELECT ... WHERE status IN ('queued',...)  → no row found   ← race
  Pod A: INSERT scan
  Pod B: INSERT scan   ← duplicate!

Fix: Redis SETNX lock (scan_lock:{repo_id}) with 15-minute TTL.
If Redis is unavailable we fall back to DB-only check (still better than
nothing for single-pod deploys; document the limitation).

Repo Isolation
──────────────
All score/history queries accept an optional repo_id parameter.
When provided, results are strictly scoped to that repository.
When omitted, the latest scan across all repos for the tenant is used
(useful for the "all repos" overview mode).
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import Scan, Repository
from app.services.base import BaseService
from app.utils.logger import logger

_REDIS_LOCK_TTL = 900  # 15 minutes


class ScanService(BaseService):

    # ─────────────────────────────────────────────────────────────────────────
    # Repository queries
    # ─────────────────────────────────────────────────────────────────────────

    async def list_repos(self, tenant_id: str) -> list[Repository]:
        result = await self.db.execute(
            select(Repository)
            .where(Repository.tenant_id == tenant_id)
            .order_by(Repository.full_name)
        )
        return list(result.scalars().all())

    # ─────────────────────────────────────────────────────────────────────────
    # Scan creation (with distributed lock)
    # ─────────────────────────────────────────────────────────────────────────

    async def create_scan(
        self,
        tenant_id: str,
        repo_id: str,
        triggered_by: str,
        branch: Optional[str] = None,
    ) -> Scan:
        """
        Create and persist a new Scan record in 'queued' state.

        Raises:
            RepoNotFoundError      — repo does not belong to this tenant
            ScanAlreadyRunningError — a concurrent scan is already in progress
        """
        from app.api.v1.endpoints.security_scan import (
            RepoNotFoundError,
            ScanAlreadyRunningError,
        )

        # ── 1. Verify repo ownership ──────────────────────────────────────────
        result = await self.db.execute(
            select(Repository).where(
                Repository.id == repo_id,
                Repository.tenant_id == tenant_id,
            )
        )
        repo = result.scalar_one_or_none()
        if not repo:
            raise RepoNotFoundError(f"Repository {repo_id!r} not found for this tenant")

        logger.info(
            f"[scan:create] repo={repo.full_name} tenant={tenant_id[:8]} "
            f"triggered_by={triggered_by[:8]}"
        )

        # ── 2. Distributed lock (Redis SETNX) ────────────────────────────────
        lock_acquired = await self._acquire_scan_lock(repo_id)
        if not lock_acquired:
            raise ScanAlreadyRunningError(
                f"A scan is already running for repository {repo.full_name!r}. "
                "Wait for it to complete before triggering a new scan."
            )

        # ── 3. Belt-and-suspenders: DB check (catches stale locks after restart)
        from datetime import timedelta
        from sqlalchemy import update as _update

        STALE_AFTER_MINUTES = 12

        existing = await self.db.execute(
            select(Scan).where(
                Scan.repo_id == repo_id,
                Scan.status.in_(["queued", "cloning", "scanning", "analyzing"]),
            ).limit(1)
        )
        running = existing.scalar_one_or_none()
        if running:
            stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_AFTER_MINUTES)
            ref_time = running.started_at or running.created_at
            normalized = (ref_time.replace(tzinfo=timezone.utc) if ref_time.tzinfo is None else ref_time)
            if ref_time and normalized < stale_cutoff:
                logger.warning(
                    f"[scan:{running.id}] Auto-failing stale scan for repo={repo.full_name} "
                    f"(running since {ref_time})"
                )
                await self.db.execute(
                    _update(Scan).where(Scan.id == running.id).values(
                        status="failed",
                        error_message=f"Auto-failed: exceeded {STALE_AFTER_MINUTES}-minute limit",
                        completed_at=datetime.now(timezone.utc),
                    )
                )
                await self.db.commit()
            else:
                await self._release_scan_lock(repo_id)
                raise ScanAlreadyRunningError(
                    f"A scan is already running for repository {repo.full_name!r}"
                )

        # ── 4. Create scan record ─────────────────────────────────────────────
        scan = Scan(
            tenant_id=tenant_id,
            repo_id=repo_id,
            triggered_by=triggered_by,
            branch=branch or repo.default_branch or "main",
            status="queued",
        )
        self.db.add(scan)
        await self.db.commit()
        await self.db.refresh(scan)

        logger.info(
            f"[scan:{scan.id}] Queued for repo={repo.full_name} "
            f"branch={scan.branch} triggered_by={triggered_by}"
        )
        return scan

    # ─────────────────────────────────────────────────────────────────────────
    # Scan dispatch
    # ─────────────────────────────────────────────────────────────────────────

    async def dispatch_scan(self, scan_id: str) -> None:
        """
        Dispatch scan execution:
          1. Try Celery with active-worker check (preferred)
          2. Fall back to asyncio background task with hard 10-minute timeout
        """
        try:
            from app.tasks.run_scan import run_security_scan
            from app.core.celery_app import celery_app

            if celery_app is None:
                raise RuntimeError("Celery not configured")

            def _check_workers() -> bool:
                try:
                    queues = celery_app.control.inspect(timeout=1.0).active_queues() or {}
                    return bool(queues)
                except Exception:
                    return False

            has_worker = await asyncio.get_event_loop().run_in_executor(None, _check_workers)

            if has_worker:
                run_security_scan.delay(scan_id)
                logger.info(f"[scan:{scan_id}] Dispatched to Celery worker")
                return
            else:
                logger.info(f"[scan:{scan_id}] No active Celery workers — using inline fallback")

        except Exception as exc:
            logger.warning(
                f"[scan:{scan_id}] Celery unavailable ({exc}) — "
                "falling back to inline async execution"
            )

        asyncio.create_task(self._run_inline_with_timeout(scan_id))

    async def _run_inline_with_timeout(self, scan_id: str) -> None:
        from app.tasks.run_scan import _run_scan_async
        try:
            await asyncio.wait_for(_run_scan_async(scan_id), timeout=300)
        except asyncio.TimeoutError:
            logger.error(f"[scan:{scan_id}] Timed out after 5 minutes")
            await self._mark_scan_failed_isolated(scan_id, "Scan timed out after 5 minutes")
        except Exception as exc:
            logger.error(f"[scan:{scan_id}] Inline execution failed: {exc}", exc_info=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Scan reads
    # ─────────────────────────────────────────────────────────────────────────

    async def get_scan(self, scan_id: str, tenant_id: str) -> Optional[dict]:
        result = await self.db.execute(
            select(Scan).where(Scan.id == scan_id, Scan.tenant_id == tenant_id)
        )
        scan = result.scalar_one_or_none()
        if not scan:
            return None
        return _scan_to_dict(scan)

    async def get_scan_history(
        self,
        tenant_id: str,
        limit: int = 30,
        repo_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Returns scan history for the Threat Timeline chart.
        Pass repo_id to scope history to a single repository.
        Each entry: {date, score, critical, high, medium, low, secrets, repo, repo_id, scan_id, status}

        Includes BOTH completed and failed scans (audit traceability — never
        silently drop failed runs). The frontend uses the `status` field to
        mark entries red when the scan errored.
        """
        query = (
            select(Scan, Repository.full_name)
            .join(Repository, Scan.repo_id == Repository.id, isouter=True)
            .where(Scan.tenant_id == tenant_id)
        )

        if repo_id:
            query = query.where(Scan.repo_id == repo_id)
            logger.info(
                f"[scan:history] ISOLATED to repo_id={repo_id[:8]} "
                f"tenant={tenant_id[:8]} limit={limit}"
            )
        else:
            logger.info(
                f"[scan:history] All repos for tenant={tenant_id[:8]} limit={limit}"
            )

        query = query.order_by(Scan.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        rows = list(result.all())

        history = [
            {
                "date": (
                    s.completed_at.isoformat()
                    if s.completed_at
                    else s.created_at.isoformat()
                ),
                "score":    s.security_score or 0,
                "critical": s.critical_count,
                "high":     s.high_count,
                "medium":   s.medium_count,
                "low":      s.low_count,
                "secrets":  s.secret_count,
                "repo":     repo_name,
                "repo_id":  s.repo_id,
                "scan_id":  s.id,
                "status":   s.status,
                "error_message": s.error_message,
                "duration_secs": s.duration_secs,
                "branch":      s.branch,
                "commit_sha":  s.commit_sha,
            }
            for s, repo_name in reversed(rows)  # chronological order
        ]
        logger.debug(
            f"[scan:history] returned {len(history)} entries "
            f"repo_id={repo_id}"
        )
        return history

    async def get_latest_score(
        self,
        tenant_id: str,
        repo_id: Optional[str] = None,
    ) -> dict:
        """
        Returns the latest security score for the dashboard.
        Pass repo_id to get the score for a specific repository only.
        Without repo_id, returns the most recent scan across all repos.

        The `breakdown` field is computed from `raw_results` (real per-scanner
        penalty values from the scan engine), NOT from score-minus-arbitrary-N.
        Scanners that were SKIPPED (e.g. container with no Dockerfile) return
        `null` so the frontend can render "N/A" instead of a synthetic 0.
        """
        from sqlalchemy import desc

        query = (
            select(
                Scan.security_score,
                Scan.ai_summary,
                Scan.ai_suggestions,
                Scan.completed_at,
                Scan.repo_id,
                Scan.raw_results,
                Scan.critical_count,
                Scan.high_count,
                Scan.medium_count,
                Scan.low_count,
                Scan.secret_count,
                Scan.misconfig_count,
                Scan.scanners_run,
                Repository.full_name,
            )
            .join(Repository, Scan.repo_id == Repository.id, isouter=True)
            .where(Scan.tenant_id == tenant_id, Scan.status == "completed")
        )

        if repo_id:
            query = query.where(Scan.repo_id == repo_id)
            logger.info(
                f"[scan:score] ISOLATED to repo_id={repo_id[:8]} "
                f"tenant={tenant_id[:8]}"
            )
        else:
            logger.info(
                f"[scan:score] Latest across all repos for tenant={tenant_id[:8]}"
            )

        result = await self.db.execute(query.order_by(desc(Scan.completed_at)).limit(1))
        row = result.fetchone()

        if not row:
            logger.info(f"[scan:score] No scan found for tenant={tenant_id[:8]} repo_id={repo_id}")
            return {
                "score":         None,
                "status":        "no_scan",
                "repo_id":       repo_id,
                "repo_name":     None,
                "ai_summary":    "No security scans have been run yet. Trigger a scan from the Security Center to get your security score.",
                "ai_suggestions": [
                    "Connect a GitHub or GitLab integration to enable repository scanning",
                    "Trigger your first security scan to establish a baseline score",
                    "Review the Security Center to configure scan settings",
                ],
                "last_scan_at":  None,
                "breakdown": None,
            }

        (scan_score, ai_summary, ai_suggestions, completed_at,
         scanned_repo_id, raw_results,
         critical, high, medium, low, secrets, misconfig,
         scanners_run, scanned_repo_name) = row

        breakdown = _compute_per_scanner_health(
            raw_results=raw_results or {},
            scanners_run=scanners_run or {},
        )

        logger.info(
            f"[scan:score] score={scan_score} repo={scanned_repo_name} "
            f"repo_id={repo_id} breakdown={breakdown}"
        )

        if scan_score is None:
            return {
                "score":         None,
                "status":        "no_score",
                "repo_id":       scanned_repo_id,
                "repo_name":     scanned_repo_name,
                "ai_summary":    ai_summary,
                "ai_suggestions": ai_suggestions or [],
                "last_scan_at":  completed_at.isoformat() if completed_at else None,
                "breakdown":     breakdown,
            }

        # Determine AI source: was this from a real LLM or the findings-driven fallback?
        import os as _os
        _has_llm = bool(_os.getenv("ANTHROPIC_API_KEY", "").strip())
        _ai_source = "llm" if _has_llm else "fallback"

        return {
            "score":          scan_score,
            "status":         "completed",
            "repo_id":        scanned_repo_id,
            "repo_name":      scanned_repo_name,
            "ai_summary":     ai_summary,
            "ai_suggestions": ai_suggestions or [],
            "ai_source":      _ai_source,
            "last_scan_at":   completed_at.isoformat() if completed_at else None,
            "breakdown":      breakdown,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Distributed lock helpers (Redis SETNX)
    # ─────────────────────────────────────────────────────────────────────────

    async def _acquire_scan_lock(self, repo_id: str) -> bool:
        try:
            from app.core.redis_client import get_redis
            redis = await get_redis()
            lock_key = f"scan_lock:{repo_id}"
            result = await redis.set(lock_key, "1", nx=True, ex=_REDIS_LOCK_TTL)
            return result is not None
        except Exception as exc:
            logger.warning(
                f"Redis lock unavailable for repo {repo_id} ({exc}) — "
                "falling back to DB-only deduplication check"
            )
            return True

    async def _release_scan_lock(self, repo_id: str) -> None:
        try:
            from app.core.redis_client import get_redis
            redis = await get_redis()
            await redis.delete(f"scan_lock:{repo_id}")
        except Exception:
            pass

    @staticmethod
    async def _mark_scan_failed_isolated(scan_id: str, error: str) -> None:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Scan).where(Scan.id == scan_id))
            scan = result.scalar_one_or_none()
            if scan and scan.status not in ("completed", "failed"):
                scan.status = "failed"
                scan.error_message = error[:1000]
                scan.completed_at = datetime.now(timezone.utc)
                await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Per-scanner health computation
# ─────────────────────────────────────────────────────────────────────────────

# Penalty per finding, mirroring ScoreCalculator in scan_engine.py
# These are NOT arbitrary — they mirror the cap logic in
# scan_engine.ScoreCalculator so a UI gauge rounds-trips back to a real number.
_SAST_PEN      = {"critical": 20, "high": 10, "medium": 5, "low": 1}
_SAST_CAP      = {"critical": 40, "high": 30, "medium": 15, "low": 5}
_DEPS_PEN      = {"critical": 20, "high": 10, "medium": 5, "low": 1}
_DEPS_CAP      = {"critical": 40, "high": 30, "medium": 15, "low": 5}
_SECRET_PEN    = 25
_SECRET_CAP    = 50
_CONTAINER_PEN = 8
_CONTAINER_CAP = 16
_CICD_PEN      = 8
_CICD_CAP      = 16

# Cap of 100 mirrors scan_engine.ScoreCalculator.compute
_HEALTH_CAP = 100


def _per_scanner_penalty(
    findings: dict | list | None,
    per: dict | int,
    cap: dict | int,
) -> float:
    """
    Sum the penalty of a scanner's findings, capped per-severity and total.
    `per` and `cap` may be either {severity: int} dicts or flat ints.
    Returns 0.0 for no findings.
    """
    if not findings:
        return 0.0
    if isinstance(findings, list):
        # items: [{severity, ...}, ...]
        grouped: dict[str, int] = {}
        for f in findings:
            sev = (f.get("severity") or f.get("level") or "low").lower()
            grouped[sev] = grouped.get(sev, 0) + 1
        findings = grouped

    total = 0.0
    for sev, count in (findings or {}).items():
        if isinstance(per, dict):
            p = per.get(sev, 0)
            c = cap.get(sev, 999)
        else:
            p = per
            c = cap
        total += min(int(count) * p, c)
    return total


def _compute_per_scanner_health(
    raw_results: dict,
    scanners_run: dict,
) -> dict:
    """
    Build a per-scanner health breakdown (0..100) from real `raw_results`.

    Returns:
        {
          "sast":      100,        # 100 means clean, 0 means full of critical findings
          "deps":      75,
          "secrets":   null,       # scanner skipped (not applicable to this repo)
          "container": 90,
          "cicd":      null,
        }

    A scanner is "skipped" if scanners_run[key] == "skipped" OR it never ran.
    We never fabricate a 0/100 for a scanner that didn't run.
    """
    breakdown: dict[str, float | None] = {
        "sast":      None,
        "deps":      None,
        "secrets":   None,
        "container": None,
        "cicd":      None,
    }

    def _ran(key: str) -> bool:
        s = (scanners_run or {}).get(key)
        return s in ("completed", "running", "ok") or (s not in ("skipped", "failed", "not_applicable") and s is not None)

    # ── SAST ───────────────────────────────────────────────────────────────
    sast_findings = (
        (raw_results or {}).get("sast")
        or (raw_results or {}).get("sast_findings")
        or {}
    )
    if _ran("sast"):
        pen = _per_scanner_penalty(sast_findings, _SAST_PEN, _SAST_CAP)
        breakdown["sast"] = round(max(0.0, _HEALTH_CAP - pen), 1)

    # ── Deps ───────────────────────────────────────────────────────────────
    deps_findings = (
        (raw_results or {}).get("deps")
        or (raw_results or {}).get("dependency")
        or (raw_results or {}).get("dependencies")
        or {}
    )
    if _ran("deps"):
        pen = _per_scanner_penalty(deps_findings, _DEPS_PEN, _DEPS_CAP)
        breakdown["deps"] = round(max(0.0, _HEALTH_CAP - pen), 1)

    # ── Secrets ────────────────────────────────────────────────────────────
    secrets_findings = (
        (raw_results or {}).get("secrets")
        or (raw_results or {}).get("secret")
        or {}
    )
    if isinstance(secrets_findings, dict):
        secret_count = int(secrets_findings.get("count", 0))
    elif isinstance(secrets_findings, list):
        secret_count = len(secrets_findings)
    elif isinstance(secrets_findings, (int, float)):
        secret_count = int(secrets_findings)
    else:
        secret_count = 0
    if _ran("secrets"):
        pen = min(secret_count * _SECRET_PEN, _SECRET_CAP)
        breakdown["secrets"] = round(max(0.0, _HEALTH_CAP - pen), 1)

    # ── Container ──────────────────────────────────────────────────────────
    container_findings = (
        (raw_results or {}).get("container")
        or (raw_results or {}).get("containers")
        or {}
    )
    if _ran("container"):
        if isinstance(container_findings, dict):
            c_count = int(container_findings.get("count", 0))
        elif isinstance(container_findings, list):
            c_count = len(container_findings)
        else:
            c_count = 0
        pen = min(c_count * _CONTAINER_PEN, _CONTAINER_CAP)
        breakdown["container"] = round(max(0.0, _HEALTH_CAP - pen), 1)

    # ── CI/CD ──────────────────────────────────────────────────────────────
    cicd_findings = (
        (raw_results or {}).get("cicd")
        or (raw_results or {}).get("ci_cd")
        or {}
    )
    if _ran("cicd"):
        if isinstance(cicd_findings, dict):
            ci_count = int(cicd_findings.get("count", 0))
        elif isinstance(cicd_findings, list):
            ci_count = len(cicd_findings)
        else:
            ci_count = 0
        pen = min(ci_count * _CICD_PEN, _CICD_CAP)
        breakdown["cicd"] = round(max(0.0, _HEALTH_CAP - pen), 1)

    return breakdown


# ─────────────────────────────────────────────────────────────────────────────
# Serializer
# ─────────────────────────────────────────────────────────────────────────────

def _scan_to_dict(scan: Scan) -> dict:
    return {
        "id":             scan.id,
        "repo_id":        scan.repo_id,
        "branch":         scan.branch,
        "status":         scan.status,
        "error_message":  scan.error_message,
        "started_at":     scan.started_at.isoformat() if scan.started_at else None,
        "completed_at":   scan.completed_at.isoformat() if scan.completed_at else None,
        "duration_secs":  scan.duration_secs,
        "scanners_run":   scan.scanners_run,
        "critical_count": scan.critical_count,
        "high_count":     scan.high_count,
        "medium_count":   scan.medium_count,
        "low_count":      scan.low_count,
        "secret_count":   scan.secret_count,
        "misconfig_count":scan.misconfig_count,
        "security_score": scan.security_score,
        "ai_summary":     scan.ai_summary,
        "ai_suggestions": scan.ai_suggestions,
        "created_at":     scan.created_at.isoformat(),
    }
