from __future__ import annotations
"""
DevSecOps Scan Worker
=====================
Celery task that drives the full scan lifecycle:
  1. Load scan + repo + integration from DB
  2. Run ScanOrchestrator (all 5 scanners)
  3. Persist Threats + Vulnerabilities
  4. Update scan record (status, score, AI summary)
  5. Update repository.last_scan_score
  6. Release the distributed scan lock (Redis)

CHANGES vs original
───────────────────
1. Redis lock is always released on completion or failure.
   Original never released the lock — it relied purely on TTL expiry.
   This meant a 15-minute dead window after every scan even when the scan
   finished in 2 minutes.
2. _safe_decrypt() moved to encryption utils — no local copy needed.
3. Retry logic tightened: max_retries=2, countdown backs off exponentially.
4. scan.status transition is validated before overwriting (idempotent: if
   another process already marked it completed/failed, we skip the update).
5. DB session is opened once and reused throughout; commit is at the end
   rather than after each status update to reduce round-trips.
   (Status commits during long scans use a flush so the poller can see them.)
"""
import asyncio
from datetime import datetime, timezone

from app.utils.logger import logger

# ─────────────────────────────────────────────────────────────────────────────
# Celery task definition
# ─────────────────────────────────────────────────────────────────────────────

try:
    from app.core.celery_app import celery_app

    @celery_app.task(
        name="app.tasks.run_scan.run_security_scan",
        bind=True,
        max_retries=2,
        default_retry_delay=60,
        soft_time_limit=1800,   # 30 min → SoftTimeLimitExceeded
        time_limit=2000,        # 33 min → hard SIGKILL
    )
    def run_security_scan(self, scan_id: str) -> None:
        """Celery entry point — wraps the async implementation."""
        try:
            asyncio.run(_run_scan_async(scan_id))
        except Exception as exc:
            logger.error(f"[scan:{scan_id}] Celery task failed: {exc}", exc_info=True)
            asyncio.run(_mark_scan_failed(scan_id, str(exc)))
            # Exponential back-off: 60s, 120s
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)

except Exception:
    # Celery not installed or broker unreachable at import time.
    # This is expected in unit-test environments — task will be called inline.
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Core async implementation (called by Celery task and by inline fallback)
# ─────────────────────────────────────────────────────────────────────────────

async def _run_scan_async(scan_id: str) -> None:
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.integration import Integration
    from app.models.scan import Repository, Scan
    from app.models.threat import Threat
    from app.models.vulnerability import Vulnerability
    from app.services.scan_engine import (
        AiAnalyzer,
        ResultAdapter,
        ScoreCalculator,
        ScanOrchestrator,
    )
    from app.utils.encryption import decrypt

    async with AsyncSessionLocal() as db:

        # ── Load scan ─────────────────────────────────────────────────────────
        res = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = res.scalar_one_or_none()
        if not scan:
            logger.error(f"[scan:{scan_id}] Record not found — aborting")
            return

        # Guard: don't re-run a scan that was already completed/failed
        if scan.status in ("completed", "failed"):
            logger.info(f"[scan:{scan_id}] Already in terminal state '{scan.status}' — skipping")
            return

        # ── Load repository ───────────────────────────────────────────────────
        res = await db.execute(select(Repository).where(Repository.id == scan.repo_id))
        repo = res.scalar_one_or_none()
        if not repo:
            await _mark_scan_failed(scan_id, "Repository record not found", db)
            return

        # ── Load integration tokens (never logged) ────────────────────────────
        github_token = ""
        gitlab_token = ""
        if repo.integration_id:
            res = await db.execute(
                select(Integration).where(Integration.id == repo.integration_id)
            )
            integration = res.scalar_one_or_none()
            if integration:
                creds = _safe_decrypt_all(integration.credentials or {})
                if repo.provider == "github":
                    github_token = creds.get("token") or creds.get("access_token", "")
                elif repo.provider == "gitlab":
                    gitlab_token = creds.get("token") or creds.get("access_token", "")

        # ── Status: queued → cloning ──────────────────────────────────────────
        scan.status = "cloning"
        scan.started_at = datetime.now(timezone.utc)
        await db.flush()  # poller can see the status update without a full commit

        try:
            # ── Status: cloning → scanning ────────────────────────────────────
            scan.status = "scanning"
            await db.flush()

            orchestrator = ScanOrchestrator(
                github_token=github_token,
                gitlab_token=gitlab_token,
            )
            result = await orchestrator.run(
                clone_url=repo.clone_url or "",
                branch=scan.branch or repo.default_branch or "main",
                provider=repo.provider,
                tenant_id=scan.tenant_id,
                scan_id=scan_id,
                repo_full_name=repo.full_name,
            )

            # ── Status: scanning → analyzing ──────────────────────────────────
            scan.status = "analyzing"
            await db.flush()

            # ── Persist findings ──────────────────────────────────────────────
            threat_dicts = ResultAdapter.to_threats(
                result.findings, scan.tenant_id, scan_id, repo.full_name
            )
            vuln_dicts = ResultAdapter.to_vulnerabilities(
                result.findings, scan.tenant_id, scan_id, repo.full_name
            )

            for td in threat_dicts:
                db.add(Threat(**td))
            for vd in vuln_dicts:
                db.add(Vulnerability(**vd))

            # ── Score + AI ────────────────────────────────────────────────────
            security_score = ScoreCalculator.compute(result.findings)
            ai_summary, ai_suggestions = await AiAnalyzer().analyze(
                repo_name=repo.full_name,
                findings=result.findings,
                score=security_score,
            )

            # ── Finalize scan record ──────────────────────────────────────────
            now = datetime.now(timezone.utc)
            scan.status = "completed"
            scan.completed_at = now
            scan.duration_secs = int((now - scan.started_at).total_seconds())
            scan.scanners_run = result.scanners_run
            scan.raw_results = {
                k: v[:50] for k, v in result.raw_by_scanner.items()
            }
            scan.critical_count = sum(1 for f in result.findings if f.severity == "critical")
            scan.high_count = sum(1 for f in result.findings if f.severity == "high")
            scan.medium_count = sum(1 for f in result.findings if f.severity == "medium")
            scan.low_count = sum(1 for f in result.findings if f.severity == "low")
            scan.secret_count = sum(1 for f in result.findings if f.scanner == "secrets")
            scan.misconfig_count = sum(
                1 for f in result.findings if f.scanner in ("cicd", "container")
            )
            scan.security_score = security_score
            scan.ai_summary = ai_summary
            scan.ai_suggestions = ai_suggestions

            repo.last_scan_at = now
            repo.last_scan_score = security_score

            await db.commit()

            logger.info(
                f"[scan:{scan_id}] Completed ✓ "
                f"score={security_score} findings={len(result.findings)} "
                f"threats={len(threat_dicts)} vulns={len(vuln_dicts)}"
            )

        except Exception as exc:
            logger.error(f"[scan:{scan_id}] Execution failed: {exc}", exc_info=True)
            await db.rollback()
            # Re-fetch scan after rollback
            res = await db.execute(select(Scan).where(Scan.id == scan_id))
            scan = res.scalar_one_or_none()
            if scan:
                scan.status = "failed"
                scan.error_message = str(exc)[:1000]
                scan.completed_at = datetime.now(timezone.utc)
                await db.commit()
            raise

        finally:
            # Always release the distributed lock so the next scan can start
            await _release_scan_lock(repo.id if repo else "")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _mark_scan_failed(scan_id: str, error: str, db=None) -> None:
    """Mark a scan as failed. Creates a new session if one isn't provided."""
    from sqlalchemy import select
    from app.models.scan import Scan

    async def _do(session) -> None:
        res = await session.execute(select(Scan).where(Scan.id == scan_id))
        scan = res.scalar_one_or_none()
        if scan and scan.status not in ("completed", "failed"):
            scan.status = "failed"
            scan.error_message = error[:1000]
            scan.completed_at = datetime.now(timezone.utc)
            await session.commit()

    if db is not None:
        await _do(db)
    else:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await _do(session)


def _safe_decrypt_all(credentials: dict) -> dict:
    """
    Attempt to decrypt all fields in a credentials dict.
    Fields that fail decryption (e.g. stored as plaintext) are returned as-is.
    IMPORTANT: never log the returned dict.
    """
    from app.utils.encryption import decrypt

    result: dict = {}
    for k, v in credentials.items():
        try:
            result[k] = decrypt(str(v)) if v else v
        except Exception:
            result[k] = v  # may already be plaintext
    return result


async def _release_scan_lock(repo_id: str) -> None:
    """Release the distributed Redis scan lock for repo_id."""
    if not repo_id:
        return
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        await redis.delete(f"scan_lock:{repo_id}")
        logger.debug(f"[lock] Released scan lock for repo {repo_id}")
    except Exception as exc:
        logger.debug(f"[lock] Failed to release scan lock for repo {repo_id}: {exc}")
        # Non-critical — lock will expire via TTL
