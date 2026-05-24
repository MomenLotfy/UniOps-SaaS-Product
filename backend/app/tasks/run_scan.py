from __future__ import annotations
"""
DevSecOps Scan Worker
=====================
Drives the full scan lifecycle with COMMITTED status transitions so the
polling endpoint always sees up-to-date progress.

KEY FIX: Replaced `await db.flush()` with direct SQL UPDATE + commit for every
status transition.  flush() only flushes within the current transaction — other
connections (the HTTP poller) cannot see uncommitted rows.  Using explicit
UPDATE + commit ensures every transition is immediately visible.
"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.utils.logger import logger


# ─────────────────────────────────────────────────────────────────────────────
# Celery task definition (optional — falls back to inline if Celery missing)
# ─────────────────────────────────────────────────────────────────────────────

try:
    from app.core.celery_app import celery_app

    @celery_app.task(
        name="app.tasks.run_scan.run_security_scan",
        bind=True,
        max_retries=2,
        default_retry_delay=60,
        soft_time_limit=1800,
        time_limit=2000,
    )
    def run_security_scan(self, scan_id: str) -> None:
        try:
            asyncio.run(_run_scan_async(scan_id))
        except Exception as exc:
            logger.error(f"[scan:{scan_id}] Celery task failed: {exc}", exc_info=True)
            asyncio.run(_mark_scan_failed(scan_id, str(exc)))
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)

except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Core async implementation
# ─────────────────────────────────────────────────────────────────────────────

async def _run_scan_async(scan_id: str) -> None:
    from app.core.database import CelerySessionLocal
    from app.models.integration import Integration
    from app.models.scan import Repository, Scan
    from app.models.threat import Threat
    from app.models.vulnerability import Vulnerability
    from app.services.scan_engine import (
        AiAnalyzer, CloneError, ResultAdapter, ScoreCalculator, ScanOrchestrator,
    )

    async with CelerySessionLocal() as db:

        # ── Load scan ─────────────────────────────────────────────────────────
        scan = await _fetch_scan(db, scan_id)
        if not scan:
            logger.error(f"[scan:{scan_id}] Record not found — aborting")
            return

        if scan.status in ("completed", "failed"):
            logger.info(f"[scan:{scan_id}] Already terminal '{scan.status}' — skip")
            return

        # ── Load repository ───────────────────────────────────────────────────
        res = await db.execute(select(Repository).where(Repository.id == scan.repo_id))
        repo = res.scalar_one_or_none()
        if not repo:
            await _set_status(db, scan_id, "failed",
                              error="Repository record not found")
            return

        # ── Extract all values we need BEFORE any commit ──────────────────────
        # After each commit SQLAlchemy expires ORM objects; storing scalars avoids
        # AttributeError on lazy attribute access post-commit.
        tenant_id      = scan.tenant_id
        repo_id        = repo.id
        clone_url      = repo.clone_url or ""
        full_name      = repo.full_name
        provider       = repo.provider
        scan_branch    = scan.branch or repo.default_branch or "main"
        integration_id = repo.integration_id

        # ── Load integration tokens ───────────────────────────────────────────
        github_token = ""
        gitlab_token = ""
        if integration_id:
            res = await db.execute(
                select(Integration).where(Integration.id == integration_id)
            )
            integration = res.scalar_one_or_none()
            if integration:
                creds = _safe_decrypt_all(integration.credentials or {})
                if provider == "github":
                    github_token = creds.get("token") or creds.get("access_token", "")
                elif provider == "gitlab":
                    gitlab_token = creds.get("token") or creds.get("access_token", "")

        # ── Validate we have a clone URL ──────────────────────────────────────
        if not clone_url:
            await _set_status(
                db, scan_id, "failed",
                error=(
                    "No clone URL configured for this repository. "
                    "Sync repositories from Settings → Integrations first."
                ),
                completed_at=datetime.now(timezone.utc),
            )
            await _release_scan_lock(repo_id)
            return

        orchestrator = ScanOrchestrator(
            github_token=github_token,
            gitlab_token=gitlab_token,
        )

        # ── queued → cloning (COMMIT — poller sees it immediately) ───────────
        now_start = datetime.now(timezone.utc)
        await _set_status(db, scan_id, "cloning", started_at=now_start)
        logger.info(
            f"[scan:{scan_id}] Status → cloning "
            f"(repo={full_name} branch={scan_branch} "
            f"has_token={bool(github_token or gitlab_token)})"
        )

        # ── Attempt git clone (raises CloneError on failure) ─────────────────
        work_dir: str | None = None
        try:
            work_dir = await orchestrator.clone(
                clone_url, scan_branch, scan_id, provider
            )
        except CloneError as exc:
            logger.error(f"[scan:{scan_id}] Clone failed: {exc}")
            await _set_status(
                db, scan_id, "failed",
                error=str(exc),
                completed_at=datetime.now(timezone.utc),
            )
            await _release_scan_lock(repo_id)
            return

        # ── Clone succeeded → run scanners ────────────────────────────────────
        try:
            # cloning → scanning (COMMIT)
            await _set_status(db, scan_id, "scanning")
            logger.info(f"[scan:{scan_id}] Status → scanning")

            result = await orchestrator.scan_repo(work_dir, scan_id, full_name)

            # scanning → analyzing (COMMIT)
            await _set_status(db, scan_id, "analyzing")
            logger.info(
                f"[scan:{scan_id}] Status → analyzing "
                f"({len(result.findings)} findings)"
            )

            # ── Persist findings ──────────────────────────────────────────────
            # Pass repo_id so every Threat/Vulnerability record carries the
            # repository it came from — enables strict per-repo isolation on reads.
            threat_dicts = ResultAdapter.to_threats(
                result.findings, tenant_id, scan_id, full_name, repo_id=repo_id
            )
            vuln_dicts = ResultAdapter.to_vulnerabilities(
                result.findings, tenant_id, scan_id, full_name, repo_id=repo_id
            )
            logger.info(
                f"[scan:{scan_id}] Persisting "
                f"{len(threat_dicts)} threats, {len(vuln_dicts)} vulnerabilities"
            )

            for td in threat_dicts:
                db.add(Threat(**td))
            for vd in vuln_dicts:
                db.add(Vulnerability(**vd))

            # ── Score + AI ────────────────────────────────────────────────────
            security_score = ScoreCalculator.compute(result.findings)
            ai_summary, ai_suggestions = await AiAnalyzer().analyze(
                repo_name=full_name,
                findings=result.findings,
                score=security_score,
            )

            # ── Final scan update (single UPDATE + commit) ────────────────────
            now_end  = datetime.now(timezone.utc)
            duration = int((now_end - now_start).total_seconds())

            await db.execute(
                update(Scan).where(Scan.id == scan_id).values(
                    status="completed",
                    completed_at=now_end,
                    duration_secs=duration,
                    scanners_run=result.scanners_run,
                    raw_results={k: v[:50] for k, v in result.raw_by_scanner.items()},
                    critical_count=sum(1 for f in result.findings if f.severity == "critical"),
                    high_count=sum(1 for f in result.findings if f.severity == "high"),
                    medium_count=sum(1 for f in result.findings if f.severity == "medium"),
                    low_count=sum(1 for f in result.findings if f.severity == "low"),
                    secret_count=sum(1 for f in result.findings if f.scanner == "secrets"),
                    misconfig_count=sum(
                        1 for f in result.findings if f.scanner in ("cicd", "container")
                    ),
                    security_score=security_score,
                    ai_summary=ai_summary,
                    ai_suggestions=ai_suggestions,
                )
            )
            await db.execute(
                update(Repository).where(Repository.id == repo_id).values(
                    last_scan_at=now_end,
                    last_scan_score=security_score,
                )
            )
            await db.commit()

            # ── Update compliance frameworks from scan results ─────────────────
            await _update_compliance(db, tenant_id, result.findings, security_score, now_end)

            logger.info(
                f"[scan:{scan_id}] ✓ COMPLETED — "
                f"score={security_score} findings={len(result.findings)} "
                f"threats={len(threat_dicts)} vulns={len(vuln_dicts)} duration={duration}s"
            )

        except Exception as exc:
            logger.error(f"[scan:{scan_id}] Scan execution failed: {exc}", exc_info=True)
            await db.rollback()
            await _set_status(
                db, scan_id, "failed",
                error=str(exc)[:1000],
                completed_at=datetime.now(timezone.utc),
            )
            raise

        finally:
            # Always clean up the temporary clone directory
            if work_dir:
                import shutil as _shutil
                _shutil.rmtree(work_dir, ignore_errors=True)
                logger.info(f"[scan:{scan_id}] Temp clone dir removed")
            await _release_scan_lock(repo_id)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_scan(db, scan_id: str):
    from app.models.scan import Scan
    res = await db.execute(select(Scan).where(Scan.id == scan_id))
    return res.scalar_one_or_none()


async def _set_status(
    db,
    scan_id: str,
    status: str,
    *,
    error: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    """
    Direct SQL UPDATE + commit so every status change is immediately visible
    to the polling endpoint (which runs in a separate DB connection/transaction).
    """
    from app.models.scan import Scan

    values: dict = {"status": status}
    if started_at is not None:
        values["started_at"] = started_at
    if completed_at is not None:
        values["completed_at"] = completed_at
    if error is not None:
        values["error_message"] = error[:1000]

    await db.execute(update(Scan).where(Scan.id == scan_id).values(**values))
    await db.commit()


async def _mark_scan_failed(scan_id: str, error: str, db=None) -> None:
    from app.models.scan import Scan

    async def _do(session) -> None:
        res = await session.execute(select(Scan).where(Scan.id == scan_id))
        scan = res.scalar_one_or_none()
        if scan and scan.status not in ("completed", "failed"):
            await _set_status(session, scan_id, "failed", error=error)

    if db is not None:
        await _do(db)
    else:
        from app.core.database import CelerySessionLocal
        async with CelerySessionLocal() as session:
            await _do(session)


def _safe_decrypt_all(credentials: dict) -> dict:
    from app.utils.encryption import decrypt

    result: dict = {}
    for k, v in credentials.items():
        try:
            result[k] = decrypt(str(v)) if v else v
        except Exception:
            result[k] = v
    return result


async def _release_scan_lock(repo_id: str) -> None:
    if not repo_id:
        return
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        await redis.delete(f"scan_lock:{repo_id}")
    except Exception:
        pass


async def _update_compliance(db, tenant_id: str, findings: list, security_score: float, scanned_at) -> None:
    """
    Derive compliance framework scores from scan findings and upsert them.

    Frameworks:
      OWASP Top 10       — SAST findings (code security)
      CIS Controls       — CI/CD + container misconfigs
      NIST CSF           — overall security posture (all finding types)
      PCI DSS            — secrets + dependency vulns (data security)
    """
    from app.models.compliance import Compliance

    def _score_and_counts(passed: int, total: int) -> tuple[float, str]:
        if total == 0:
            return 100.0, "compliant"
        pct = round((passed / total) * 100, 1)
        status = "compliant" if pct >= 80 else ("in_progress" if pct >= 50 else "non_compliant")
        return pct, status

    sast_total   = sum(1 for f in findings if f.scanner == "sast")
    sast_crit_hi = sum(1 for f in findings if f.scanner == "sast" and f.severity in ("critical", "high"))
    sast_pass    = max(0, sast_total - sast_crit_hi)

    cicd_cont_total = sum(1 for f in findings if f.scanner in ("cicd", "container"))
    cicd_cont_fail  = sum(1 for f in findings if f.scanner in ("cicd", "container") and f.severity in ("critical", "high"))
    cicd_pass       = max(0, cicd_cont_total - cicd_cont_fail)

    secrets_total = sum(1 for f in findings if f.scanner == "secrets")
    dep_total     = sum(1 for f in findings if f.scanner == "deps")
    pci_total     = secrets_total + dep_total
    pci_fail      = sum(1 for f in findings if f.scanner in ("secrets", "deps") and f.severity in ("critical", "high"))
    pci_pass      = max(0, pci_total - pci_fail)

    all_total = len(findings)
    all_fail  = sum(1 for f in findings if f.severity in ("critical", "high"))
    all_pass  = max(0, all_total - all_fail)

    frameworks = [
        {
            "framework": "OWASP Top 10",
            "passed": sast_pass if sast_total > 0 else 10,
            "failed": sast_crit_hi,
            "total":  max(sast_total, 10),
        },
        {
            "framework": "CIS Controls",
            "passed": cicd_pass if cicd_cont_total > 0 else 8,
            "failed": cicd_cont_fail,
            "total":  max(cicd_cont_total, 8),
        },
        {
            "framework": "NIST CSF",
            "passed": all_pass if all_total > 0 else 20,
            "failed": all_fail,
            "total":  max(all_total, 20),
        },
        {
            "framework": "PCI DSS",
            "passed": pci_pass if pci_total > 0 else 12,
            "failed": pci_fail,
            "total":  max(pci_total, 12),
        },
    ]

    for fw in frameworks:
        score, status = _score_and_counts(fw["passed"], fw["total"])
        # Upsert: find existing row for this tenant+framework
        existing = await db.execute(
            select(Compliance).where(
                Compliance.tenant_id == tenant_id,
                Compliance.framework == fw["framework"],
            )
        )
        rec = existing.scalar_one_or_none()
        if rec:
            rec.score   = score
            rec.passed  = fw["passed"]
            rec.failed  = fw["failed"]
            rec.total   = fw["total"]
            rec.status  = status
            rec.details = [{"last_scan_at": scanned_at.isoformat(), "security_score": security_score}]
        else:
            db.add(Compliance(
                tenant_id = tenant_id,
                framework = fw["framework"],
                score     = score,
                passed    = fw["passed"],
                failed    = fw["failed"],
                total     = fw["total"],
                status    = status,
                details   = [{"last_scan_at": scanned_at.isoformat(), "security_score": security_score}],
            ))

    await db.commit()
    logger.info(f"[compliance] Updated {len(frameworks)} frameworks for tenant={tenant_id[:8]}")
