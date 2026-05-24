from __future__ import annotations
"""Sync AWS Security Hub findings → threats, vulnerabilities, and compliance."""
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from app.utils.logger import logger


try:
    from app.core.celery_app import celery_app

    @celery_app.task(
        name="app.tasks.sync_security.sync_aws_security",
        bind=True, max_retries=2, default_retry_delay=300, soft_time_limit=600,
    )
    def sync_aws_security(self):
        try:
            asyncio.run(sync_aws_security_async())
            logger.info("Security sync completed")
        except Exception as exc:
            logger.error(f"Security sync failed: {exc}")
            raise self.retry(exc=exc, countdown=120)
except Exception:
    pass


async def sync_aws_security_async(tenant_id: str | None = None) -> dict:
    """Pull findings from AWS Security Hub and save to DB."""
    from app.core.database import AsyncSessionLocal
    from app.models.integration import Integration
    from app.models.threat import Threat
    from app.models.vulnerability import Vulnerability
    from app.models.compliance import Compliance
    from app.tasks.sync_costs import _decrypt_creds

    summary = {"integrations": 0, "threats": 0, "vulnerabilities": 0, "compliance": 0}

    async with AsyncSessionLocal() as db:
        query = select(Integration).where(
            Integration.is_active == True,
            Integration.status == "connected",
            Integration.type == "aws",
        )
        if tenant_id:
            query = query.where(Integration.tenant_id == tenant_id)

        result = await db.execute(query)
        integrations = result.scalars().all()

        for integration in integrations:
            try:
                creds = _decrypt_creds(integration.credentials)
                config = {**creds, **integration.config}

                from app.integrations.aws.security_hub import SecurityHub
                hub = SecurityHub(config)

                # ── Threats ───────────────────────────────────────────────
                threats = await hub.get_threats()
                for t in threats:
                    source_id = t.get("source_id", "")
                    existing = await db.execute(
                        select(Threat).where(
                            Threat.tenant_id == integration.tenant_id,
                            Threat.raw_data["finding_id"].astext == source_id,
                        )
                    ) if source_id else None

                    if existing and existing.scalar_one_or_none():
                        continue

                    db.add(Threat(
                        tenant_id=integration.tenant_id,
                        title=t["title"][:499],
                        description=t.get("description", ""),
                        severity=t.get("severity", "medium"),
                        category=t.get("category", "network"),
                        source=t.get("source", "aws_security_hub"),
                        status="open",
                        resource=t.get("resource", ""),
                        ip=t.get("ip"),
                        mitre_tactic=t.get("mitre_tactic"),
                        mitre_technique=t.get("mitre_technique"),
                        raw_data=t.get("raw_data", {}),
                    ))
                    summary["threats"] += 1

                    # ── Publish THREAT_DETECTED (non-blocking) ────────────
                    await _fire_threat_event(
                        tenant_id=str(integration.tenant_id),
                        title=t["title"][:499],
                        severity=t.get("severity", "medium"),
                        category=t.get("category", "network"),
                        source=t.get("source", "aws_security_hub"),
                        resource=t.get("resource", ""),
                        mitre_tactic=t.get("mitre_tactic"),
                    )

                # ── Vulnerabilities ───────────────────────────────────────
                vulns = await hub.get_vulnerabilities()
                for v in vulns:
                    cve = v.get("cve_id")
                    if cve:
                        existing = await db.execute(
                            select(Vulnerability).where(
                                Vulnerability.tenant_id == integration.tenant_id,
                                Vulnerability.cve_id == cve,
                            )
                        )
                        if existing.scalar_one_or_none():
                            continue

                    db.add(Vulnerability(
                        tenant_id=integration.tenant_id,
                        cve_id=v.get("cve_id"),
                        title=v["title"][:499],
                        description=v.get("description", ""),
                        severity=v.get("severity", "medium"),
                        cvss_score=v.get("cvss_score"),
                        status=v.get("status", "open"),
                        package_name=v.get("package_name"),
                        package_version=v.get("package_version"),
                        fixed_version=v.get("fixed_version"),
                        target=v.get("target", ""),
                        image=v.get("image"),
                        references=v.get("references", []),
                    ))
                    summary["vulnerabilities"] += 1

                # ── Compliance ────────────────────────────────────────────
                compliance_data = await hub.get_compliance_status()
                for c in compliance_data:
                    existing = await db.execute(
                        select(Compliance).where(
                            Compliance.tenant_id == integration.tenant_id,
                            Compliance.framework == c["framework"],
                        )
                    )
                    record = existing.scalar_one_or_none()
                    if record:
                        record.score = c["score"]
                        record.passed = c["passed"]
                        record.failed = c["failed"]
                        record.total = c["total"]
                        record.status = c["status"]
                    else:
                        db.add(Compliance(
                            tenant_id=integration.tenant_id,
                            framework=c["framework"],
                            score=c["score"],
                            passed=c["passed"],
                            failed=c["failed"],
                            total=c["total"],
                            status=c["status"],
                            details={},
                        ))
                    summary["compliance"] += 1

                integration.last_sync = datetime.now(timezone.utc)
                await db.commit()
                summary["integrations"] += 1
                logger.info(f"AWS security sync done for {integration.name}: {summary}")

            except Exception as e:
                logger.error(f"Security sync failed for {integration.id}: {e}")
                await db.rollback()

    return summary


async def _fire_threat_event(
    tenant_id: str,
    title: str,
    severity: str,
    category: str,
    source: str,
    resource: str,
    mitre_tactic: str | None,
) -> None:
    """
    Publish THREAT_DETECTED to the Redis event bus.

    Design principles:
    - Called AFTER db.add() + before db.commit() is fine because the event
      is informational — consumers (ML service, WebSocket) only need the
      metadata, not the DB primary key.
    - Non-blocking: swallows all exceptions so a Redis outage never aborts
      the security sync loop or rolls back already-inserted threats.
    - Structured payload allows ML service to auto-trigger correlation
      analysis without a separate /ml/analyze API call.
    - severity field enables the WebSocket manager to route CRITICAL threats
      to immediate browser notifications.
    """
    try:
        from app.events.bus import event_bus
        from app.events.events import EventType
        from app.api.v1.websocket.manager import ws_manager
        from app.api.v1.websocket.events import WSEventType

        # ── 1. Publish to Redis pub/sub
        await event_bus.publish(
            EventType.THREAT_DETECTED,
            payload={
                "title":        title,
                "severity":     severity,
                "category":     category,
                "source":       source,
                "resource":     resource,
                "mitre_tactic": mitre_tactic,
            },
            tenant_id=tenant_id,
        )

        # ── 2. Push to connected browser tabs instantly
        sent = await ws_manager.send_to_tenant(tenant_id, {
            "event": WSEventType.THREAT_DETECTED,
            "data": {
                "title":        title,
                "severity":     severity,
                "category":     category,
                "source":       source,
                "resource":     resource,
                "mitre_tactic": mitre_tactic,
            },
        })
        logger.info(
            f"[EventBus] THREAT_DETECTED published — "
            f"tenant={tenant_id[:8]} severity={severity} "
            f"category={category} source={source} ws_clients={sent}"
        )
    except Exception as exc:
        # Non-fatal: Redis may be temporarily unavailable.
        # Threat record is already written to PostgreSQL.
        logger.warning(
            f"[EventBus] THREAT_DETECTED publish failed (non-fatal) — "
            f"tenant={tenant_id[:8]} title={title[:60]!r}: {exc}"
        )
