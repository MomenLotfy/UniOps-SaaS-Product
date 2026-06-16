"""Celery task — runs vulnerability scans on container images and source code."""
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.celery_app import celery_app
from app.utils.logger import logger


@celery_app.task(
    name="app.tasks.scan_vulnerabilities.run_full_scan",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
    soft_time_limit=3600,
)
def run_full_scan(self):
    """Run vulnerability scans across all active integrations."""
    try:
        asyncio.run(_run_scan())
        logger.info("Vulnerability scan completed")
    except Exception as exc:
        logger.error(f"Vulnerability scan failed: {exc}")
        raise self.retry(exc=exc, countdown=300)


async def _run_scan():
    from app.core.database import CelerySessionLocal as AsyncSessionLocal
    from app.models.integration import Integration
    from app.models.vulnerability import Vulnerability
    from app.models.tenant import Tenant

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Integration).where(Integration.is_active == True, Integration.status == "connected")
        )
        integrations = result.scalars().all()

        for integration in integrations:
            try:
                if integration.type == "kubernetes":
                    await _scan_container_images(db, integration)
                elif integration.type in ("github", "gitlab"):
                    await _scan_source_code(db, integration)
            except Exception as e:
                logger.error(f"Scan failed for integration {integration.id}: {e}")


async def _scan_container_images(db, integration):
    from app.integrations.scanners.trivy import TrivyScanner
    from app.models.vulnerability import Vulnerability

    scanner = TrivyScanner({})
    is_available = await scanner.test_connection()
    if not is_available:
        logger.warning("Trivy not available, skipping container scan")
        return

    images_to_scan = integration.config.get("scan_images", [])
    for image in images_to_scan[:10]:
        try:
            vulns = await scanner.scan_image(image)
            for v in vulns:
                db.add(Vulnerability(
                    tenant_id=integration.tenant_id,
                    cve_id=v.get("cve_id"),
                    title=v.get("title", "Unknown vulnerability"),
                    description=v.get("description"),
                    severity=v.get("severity", "unknown"),
                    cvss_score=v.get("cvss_score"),
                    package_name=v.get("package_name"),
                    package_version=v.get("package_version"),
                    fixed_version=v.get("fixed_version"),
                    image=image,
                    status="open",
                ))
            await db.commit()
            logger.info(f"Found {len(vulns)} vulnerabilities in {image}")
        except Exception as e:
            logger.error(f"Failed to scan image {image}: {e}")
            await db.rollback()


async def _scan_source_code(db, integration):
    from app.integrations.scanners.semgrep import SemgrepScanner
    scanner = SemgrepScanner({})
    is_available = await scanner.test_connection()
    if not is_available:
        logger.warning("Semgrep not available, skipping source scan")
        return
    logger.info(f"Source code scan would run for integration {integration.id}")
