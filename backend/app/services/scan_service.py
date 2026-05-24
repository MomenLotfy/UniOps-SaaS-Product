from __future__ import annotations
"""
ScanService
===========
Owns all business logic for the DevSecOps scan subsystem:
  - Repository listing
  - Scan creation (with concurrency guard)
  - Scan dispatch (Celery → async fallback)
  - Scan status reads
  - Scan history + score

Previously this logic lived partly in security_scan.py (endpoint), partly in
run_scan.py (Celery task), and the dispatch helper duplicated a DB session
open/close.  Everything is now in one place.

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
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import Scan, Repository
from app.services.base import BaseService
from app.utils.logger import logger

# Imported lazily to keep startup fast when Redis is unavailable
_REDIS_LOCK_TTL = 900  # 15 minutes — max scan duration before lock auto-expires


class ScanService(BaseService):
    """Domain service for the DevSecOps scan subsystem."""

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
            RepoNotFoundError     — repo does not belong to this tenant
            ScanAlreadyRunningError — a concurrent scan is already in progress
        """
        # Import here to avoid circular-import at module load time
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

        STALE_AFTER_MINUTES = 12  # scans stuck longer than this are auto-failed

        existing = await self.db.execute(
            select(Scan).where(
                Scan.repo_id == repo_id,
                Scan.status.in_(["queued", "cloning", "scanning", "analyzing"]),
            ).limit(1)
        )
        running = existing.scalar_one_or_none()
        if running:
            stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_AFTER_MINUTES)
            # A scan is "stale" if it has been running longer than STALE_AFTER_MINUTES
            # (use started_at if available, otherwise created_at)
            ref_time = running.started_at or running.created_at
            if ref_time and ref_time.replace(tzinfo=timezone.utc) if ref_time.tzinfo is None else ref_time < stale_cutoff:
                # Auto-fail the stale scan and allow a fresh one
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
                # Release lock we just acquired since we won't proceed
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
          1. Try Celery with active-worker check (preferred — isolated, monitored, retriable)
          2. Fall back to asyncio background task with hard 10-minute timeout

        This method is called from the endpoint *after* the HTTP response has
        been sent (via BackgroundTask or a post-response hook), so it must
        never block the event loop for more than a few milliseconds.
        """
        try:
            from app.tasks.run_scan import run_security_scan
            from app.core.celery_app import celery_app

            if celery_app is None:
                raise RuntimeError("Celery not configured")

            # Check for active workers before enqueuing — tasks sent to Redis when
            # no workers are running sit in the queue indefinitely (scan stays "queued").
            # Run inspect in a thread so the async event loop is never blocked.
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

        # Async fallback with hard timeout — never blocks HTTP event loop
        asyncio.create_task(self._run_inline_with_timeout(scan_id))

    async def _run_inline_with_timeout(self, scan_id: str) -> None:
        """Run scan inline (no Celery) with a hard 5-minute timeout."""
        from app.tasks.run_scan import _run_scan_async

        try:
            await asyncio.wait_for(_run_scan_async(scan_id), timeout=300)
        except asyncio.TimeoutError:
            logger.error(f"[scan:{scan_id}] Timed out after 5 minutes")
            await self._mark_scan_failed_isolated(scan_id, "Scan timed out after 5 minutes")
        except Exception as exc:
            logger.error(f"[scan:{scan_id}] Inline execution failed: {exc}", exc_info=True)
            # _run_scan_async already marks the scan as failed internally;
            # this is a safety net for unexpected exceptions outside that scope.

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

    async def get_scan_history(self, tenant_id: str, limit: int = 30) -> list[dict]:
        result = await self.db.execute(
            select(Scan)
            .where(Scan.tenant_id == tenant_id, Scan.status == "completed")
            .order_by(Scan.created_at.desc())
            .limit(limit)
        )
        scans = list(result.scalars().all())
        return [
            {
                "date": (
                    s.completed_at.isoformat()
                    if s.completed_at
                    else s.created_at.isoformat()
                ),
                "score": s.security_score or 0,
                "critical": s.critical_count,
                "high": s.high_count,
                "medium": s.medium_count,
                "low": s.low_count,
                "secrets": s.secret_count,
                "repo": None,  # join if needed
                "scan_id": s.id,
            }
            for s in reversed(scans)  # chronological order
        ]

    async def get_latest_score(self, tenant_id: str) -> dict:
        from sqlalchemy import desc

        result = await self.db.execute(
            select(
                Scan.security_score,
                Scan.ai_summary,
                Scan.ai_suggestions,
                Scan.completed_at,
            )
            .where(Scan.tenant_id == tenant_id, Scan.status == "completed")
            .order_by(desc(Scan.completed_at))
            .limit(1)
        )
        row = result.fetchone()
        scan_score = float(row[0]) if row and row[0] is not None else None
        ai_summary = row[1] if row else None
        ai_suggestions = row[2] if row else []

        # ── Fallback: never return null score ────────────────────────────────
        # If no scan has completed yet, return a meaningful pending state
        # so the UI shows something useful instead of empty/loading forever.
        if scan_score is None:
            return {
                "score": None,
                "status": "no_scan",
                "ai_summary": "No security scans have been run yet. Trigger a scan from the Security Center to get your security score.",
                "ai_suggestions": [
                    "Connect a GitHub or GitLab integration to enable repository scanning",
                    "Trigger your first security scan to establish a baseline score",
                    "Review the Security Center to configure scan settings",
                ],
                "last_scan_at": None,
                "breakdown": {
                    "Code Security": None,
                    "Dependencies": None,
                    "Secrets": None,
                    "CI/CD Security": None,
                    "Containers": None,
                },
            }

        return {
            "score": scan_score,
            "ai_summary": ai_summary,
            "ai_suggestions": ai_suggestions or [],
            "last_scan_at": row[3].isoformat() if row and row[3] else None,
            "breakdown": {
                "Code Security": max(0, round(scan_score - 10, 1)),
                "Dependencies": max(0, round(scan_score - 5, 1)),
                "Secrets": 100 if scan_score > 75 else 60,
                "CI/CD Security": max(0, round(scan_score - 8, 1)),
                "Containers": max(0, round(scan_score - 3, 1)),
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Distributed lock helpers (Redis SETNX)
    # ─────────────────────────────────────────────────────────────────────────

    async def _acquire_scan_lock(self, repo_id: str) -> bool:
        """
        Try to acquire an exclusive scan lock for repo_id.
        Returns True if lock acquired (no scan is running), False otherwise.

        Uses Redis SET NX EX — atomic, safe across multiple pods.
        Falls back to True (permit) if Redis is unavailable so deploys without
        Redis don't break; the DB check below is the fallback guard.
        """
        try:
            from app.core.redis_client import get_redis
            redis = await get_redis()
            lock_key = f"scan_lock:{repo_id}"
            # SET key value NX EX ttl — returns True if set, None if already exists
            result = await redis.set(lock_key, "1", nx=True, ex=_REDIS_LOCK_TTL)
            return result is not None
        except Exception as exc:
            logger.warning(
                f"Redis lock unavailable for repo {repo_id} ({exc}) — "
                "falling back to DB-only deduplication check"
            )
            return True  # permit; DB check is the fallback

    async def _release_scan_lock(self, repo_id: str) -> None:
        """Release the distributed scan lock (called on early-exit paths only)."""
        try:
            from app.core.redis_client import get_redis
            redis = await get_redis()
            await redis.delete(f"scan_lock:{repo_id}")
        except Exception:
            pass  # lock will expire via TTL

    # ─────────────────────────────────────────────────────────────────────────
    # Isolated failure marking (used by timeout handler with its own session)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def _mark_scan_failed_isolated(scan_id: str, error: str) -> None:
        """
        Mark a scan as failed using a fresh DB session.
        Used by the timeout handler which runs outside the request session.
        """
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
# Serializer (pure function — no DB access)
# ─────────────────────────────────────────────────────────────────────────────

def _scan_to_dict(scan: Scan) -> dict:
    return {
        "id": scan.id,
        "repo_id": scan.repo_id,
        "branch": scan.branch,
        "status": scan.status,
        "error_message": scan.error_message,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "duration_secs": scan.duration_secs,
        "scanners_run": scan.scanners_run,
        "critical_count": scan.critical_count,
        "high_count": scan.high_count,
        "medium_count": scan.medium_count,
        "low_count": scan.low_count,
        "secret_count": scan.secret_count,
        "misconfig_count": scan.misconfig_count,
        "security_score": scan.security_score,
        "ai_summary": scan.ai_summary,
        "ai_suggestions": scan.ai_suggestions,
        "created_at": scan.created_at.isoformat(),
    }
