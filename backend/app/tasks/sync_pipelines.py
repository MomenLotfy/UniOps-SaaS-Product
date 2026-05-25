from __future__ import annotations
"""Sync GitHub / GitLab pipelines and security alerts into the database."""
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from app.utils.logger import logger

try:
    from app.core.celery_app import celery_app

    @celery_app.task(
        name="app.tasks.sync_pipelines.sync_all_pipelines",
        bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=600,
    )
    def sync_all_pipelines(self):
        try:
            asyncio.run(_sync_pipelines())
            logger.info("Pipeline sync completed")
        except Exception as exc:
            logger.error(f"Pipeline sync failed: {exc}")
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
except Exception:
    pass


async def _sync_pipelines(tenant_id: str | None = None) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.models.integration import Integration
    from app.utils.encryption import decrypt

    summary = {"integrations": 0, "pipelines": 0, "vulnerabilities": 0}

    async with AsyncSessionLocal() as db:
        query = select(Integration).where(
            Integration.is_active == True,
            Integration.status == "connected",
            Integration.type.in_(["github", "gitlab"]),
        )
        if tenant_id:
            query = query.where(Integration.tenant_id == tenant_id)

        result = await db.execute(query)
        integrations = result.scalars().all()
        logger.info(f"Syncing pipelines for {len(integrations)} integrations")

        for integration in integrations:
            try:
                creds = _decrypt_creds(integration.credentials or {})
                config = {**creds, **(integration.config or {})}

                if integration.type == "github":
                    p, v = await _sync_github(db, integration, config)
                else:
                    p, v = await _sync_gitlab(db, integration, config)

                summary["pipelines"]       += p
                summary["vulnerabilities"] += v

                integration.last_sync = datetime.now(timezone.utc)
                await db.commit()
                summary["integrations"] += 1

            except Exception as e:
                logger.error(f"Pipeline sync failed for {integration.id}: {e}")
                await db.rollback()

    return summary


async def _sync_github(db, integration, config: dict) -> tuple[int, int]:
    from app.integrations.github.client import GitHubClient
    from app.models.pipeline import Pipeline
    from app.models.vulnerability import Vulnerability

    client    = GitHubClient(config)
    tenant_id = integration.tenant_id
    repos     = config.get("repos") or []   # specific repos from integration config

    if not repos:
        all_repos = await client.list_repos(per_page=20)
        repos     = [r["full_name"] for r in all_repos[:10]]  # limit to 10 repos

    pipelines_synced = 0
    vulns_synced     = 0

    for full_name in repos:
        parts = full_name.split("/", 1)
        if len(parts) != 2:
            continue
        owner, repo = parts

        # ── Workflow runs → pipelines ─────────────────────────────────────
        runs = await client.list_workflow_runs(owner, repo, per_page=20)

        for run in runs:
            ext_id = run["id"]
            existing = await db.execute(
                select(Pipeline).where(
                    Pipeline.tenant_id     == tenant_id,
                    Pipeline.external_id   == ext_id,
                    Pipeline.repository    == full_name,
                )
            )
            pipeline = existing.scalar_one_or_none()

            if pipeline:
                # Update mutable fields
                pipeline.status      = run["status"]
                pipeline.finished_at = _parse_dt(run.get("finished_at"))
                pipeline.duration    = run.get("duration")
                pipeline.updated_at  = datetime.now(timezone.utc)
            else:
                pipeline = Pipeline(
                    tenant_id      = tenant_id,
                    integration_id = integration.id,
                    external_id    = ext_id,
                    name           = run["name"],
                    repository     = full_name,
                    branch         = run["branch"],
                    status         = run["status"],
                    triggered_by   = run.get("triggered_by"),
                    commit_sha     = run.get("commit_sha"),
                    commit_message = run.get("commit_message", "")[:500],
                    started_at     = _parse_dt(run.get("started_at")),
                    finished_at    = _parse_dt(run.get("finished_at")),
                    duration       = run.get("duration"),
                    logs_url       = run.get("logs_url"),
                    metadata_      = {"run_number": run.get("run_number"), "event": run.get("event")},
                )
                db.add(pipeline)
            pipelines_synced += 1

        # ── Dependabot alerts → vulnerabilities ───────────────────────────
        # Dependabot may be disabled or the token may lack access — treat as
        # non-fatal so pipeline data is never lost because of a missing feature.
        try:
            alerts = await client.list_dependabot_alerts(owner, repo)
        except Exception as dep_exc:
            logger.warning(
                f"Dependabot alerts skipped for {full_name} "
                f"(non-fatal): {dep_exc}"
            )
            alerts = []
        for alert in alerts:
            cve = alert.get("cve_id")
            pkg = alert.get("package")

            # Skip if already exists
            existing_vuln = await db.execute(
                select(Vulnerability).where(
                    Vulnerability.tenant_id   == tenant_id,
                    Vulnerability.target      == full_name,
                    Vulnerability.package_name == pkg,
                    *([Vulnerability.cve_id == cve] if cve else []),
                )
            )
            if existing_vuln.scalar_one_or_none():
                continue

            db.add(Vulnerability(
                tenant_id      = tenant_id,
                cve_id         = cve,
                title          = alert["title"][:499],
                description    = alert.get("description", ""),
                severity       = alert["severity"],
                cvss_score     = alert.get("cvss"),
                status         = "open" if alert.get("state") == "open" else "resolved",
                package_name   = pkg,
                fixed_version  = alert.get("fixed_in"),
                target         = full_name,
                references     = [alert["html_url"]] if alert.get("html_url") else [],
            ))
            vulns_synced += 1

        # ── Notify on failed pipelines ────────────────────────────────────
        failed = [r for r in runs if r["status"] == "failed"]
        for run in failed[:3]:  # max 3 notifications per repo per sync
            age = datetime.now(timezone.utc) - (_parse_dt(run.get("finished_at")) or datetime.now(timezone.utc))
            if age < timedelta(minutes=10):  # only notify on recently failed
                try:
                    from app.services.notification_service import NotificationService
                    await NotificationService().notify_pipeline_failure(tenant_id, {
                        "name":   run["name"],
                        "branch": run["branch"],
                        "repo":   full_name,
                        "url":    run.get("logs_url", ""),
                    })
                except Exception:
                    pass

    return pipelines_synced, vulns_synced


async def _sync_gitlab(db, integration, config: dict) -> tuple[int, int]:
    """GitLab sync — placeholder, same pattern as GitHub."""
    logger.info(f"GitLab sync for integration {integration.id} — coming soon")
    return 0, 0


def _decrypt_creds(credentials: dict) -> dict:
    from app.utils.encryption import decrypt
    result = {}
    for k, v in credentials.items():
        if k in {"token", "access_key", "secret_key", "password", "api_key"} and v:
            try:
                result[k] = decrypt(str(v))
            except Exception:
                result[k] = v
        else:
            result[k] = v
    return result


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
