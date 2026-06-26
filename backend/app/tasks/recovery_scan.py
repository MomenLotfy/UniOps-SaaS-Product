from __future__ import annotations
"""
Remediation Recovery Scan Task.
Periodically detects "stuck" remediation executions and attempts recovery/rollback.
"""
import asyncio
from app.utils.logger import logger

# ── Celery task ───────────────────────────────────────────────────────────────
try:
    from app.core.celery_app import celery_app

    @celery_app.task(
        name="app.tasks.recovery_scan.run_recovery_scan",
        bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=600,
    )
    def run_recovery_scan(self):
        try:
            asyncio.run(_run_recovery_scan_async())
            logger.info("Remediation recovery scan completed")
        except Exception as exc:
            logger.error(f"Remediation recovery scan failed: {exc}")
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
except Exception:
    pass


# ── Core async function ───────────────────────────────────────────────────────
async def _run_recovery_scan_async() -> dict:
    """
    Instantiates the RemediationManager and triggers a scan for stuck executions.
    Returns the summary of the recovery operation.
    """
    from app.core.database import CelerySessionLocal as AsyncSessionLocal
    from app.remediation.registry.registry import CapabilityRegistry
    from app.remediation.manager import RemediationManager

    async with AsyncSessionLocal() as db:
        try:
            # Initialize Registry (required by Manager)
            registry = CapabilityRegistry()

            # Instantiate Manager
            # CopilotService is optional and typically injected via FastAPI dependencies
            manager = RemediationManager(db=db, registry=registry)

            # Perform the recovery scan
            result = await manager.perform_recovery_scan()

            logger.info(f"Recovery scan result: {result}")
            return result
        except Exception as e:
            logger.exception(f"Error during remediation recovery scan: {e}")
            raise
