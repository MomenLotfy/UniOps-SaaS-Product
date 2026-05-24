from __future__ import annotations
"""GitHub webhook — processes workflow_run, push, pull_request, security_advisory events."""
import hmac, hashlib, json
from fastapi import APIRouter, Request, Header, HTTPException
from app.config import settings
from app.utils.logger import logger

router = APIRouter()

HANDLED_EVENTS = {"workflow_run", "push", "pull_request", "security_advisory", "dependabot_alert"}


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str      = Header(None),
    x_github_delivery: str   = Header(None),
):
    body = await request.body()

    # Verify signature
    if settings.GITHUB_WEBHOOK_SECRET and x_hub_signature_256:
        expected = "sha256=" + hmac.new(
            settings.GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info(f"GitHub webhook: event={x_github_event} delivery={x_github_delivery}")

    if x_github_event not in HANDLED_EVENTS:
        return {"received": True, "handled": False}

    try:
        if x_github_event == "workflow_run":
            await _handle_workflow_run(payload)
        elif x_github_event == "push":
            await _handle_push(payload)
        elif x_github_event == "security_advisory":
            await _handle_security_advisory(payload)
        elif x_github_event == "dependabot_alert":
            await _handle_dependabot_alert(payload)
    except Exception as e:
        logger.error(f"GitHub webhook handler error ({x_github_event}): {e}")

    return {"received": True, "handled": True, "event": x_github_event}


async def _handle_workflow_run(payload: dict):
    """workflow_run event → upsert pipeline in DB."""
    action = payload.get("action")   # requested, in_progress, completed
    run    = payload.get("workflow_run", {})
    repo   = payload.get("repository", {}).get("full_name", "")

    if action not in ("completed", "in_progress"):
        return

    from app.integrations.github.client import _map_status
    status = _map_status(run.get("status"), run.get("conclusion"))

    # Find the matching integration by repo
    tenant_id, integration_id = await _find_integration_for_repo(repo)
    if not tenant_id:
        logger.debug(f"No integration found for repo {repo}")
        return

    from app.core.database import AsyncSessionLocal
    from app.models.pipeline import Pipeline
    from sqlalchemy import select
    from datetime import datetime, timezone

    ext_id = str(run["id"])

    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Pipeline).where(
                Pipeline.tenant_id   == tenant_id,
                Pipeline.external_id == ext_id,
            )
        )
        pipeline = existing.scalar_one_or_none()

        if pipeline:
            pipeline.status      = status
            pipeline.finished_at = _parse_dt(run.get("updated_at")) if run.get("status") == "completed" else None
            pipeline.updated_at  = datetime.now(timezone.utc)
        else:
            duration = None
            if run.get("run_started_at") and run.get("updated_at") and run.get("status") == "completed":
                try:
                    s = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
                    e = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
                    duration = max(0, int((e - s).total_seconds()))
                except Exception:
                    pass

            db.add(Pipeline(
                tenant_id      = tenant_id,
                integration_id = integration_id,
                external_id    = ext_id,
                name           = run.get("name", run.get("display_title", "Workflow")),
                repository     = repo,
                branch         = run.get("head_branch", "main"),
                status         = status,
                triggered_by   = run.get("triggering_actor", {}).get("login"),
                commit_sha     = run.get("head_sha", "")[:7],
                commit_message = run.get("display_title", "")[:500],
                started_at     = _parse_dt(run.get("run_started_at")),
                finished_at    = _parse_dt(run.get("updated_at")) if run.get("status") == "completed" else None,
                duration       = duration,
                logs_url       = run.get("html_url"),
                metadata_      = {"event": "workflow_run", "run_number": run.get("run_number")},
            ))

        await db.commit()

    # Notify on failure
    if status == "failed":
        try:
            from app.services.notification_service import NotificationService
            await NotificationService().notify_pipeline_failure(tenant_id, {
                "name":   run.get("name", "Workflow"),
                "branch": run.get("head_branch", "main"),
                "repo":   repo,
                "url":    run.get("html_url", ""),
            })
        except Exception as e:
            logger.warning(f"Pipeline failure notification skipped: {e}")


async def _handle_push(payload: dict):
    """Push event — log only, no DB write needed."""
    repo   = payload.get("repository", {}).get("full_name", "")
    branch = payload.get("ref", "").replace("refs/heads/", "")
    commits = len(payload.get("commits", []))
    logger.info(f"GitHub push: {repo}@{branch} ({commits} commits)")


async def _handle_security_advisory(payload: dict):
    """GitHub security advisory → create vulnerability record."""
    action   = payload.get("action")
    advisory = payload.get("security_advisory", {})
    if action not in ("published", "updated"):
        return

    logger.info(f"Security advisory: {advisory.get('ghsa_id')} severity={advisory.get('severity')}")


async def _handle_dependabot_alert(payload: dict):
    """Dependabot alert → upsert vulnerability."""
    action = payload.get("action")  # created, dismissed, fixed, auto_dismissed
    alert  = payload.get("alert", {})
    repo   = payload.get("repository", {}).get("full_name", "")

    tenant_id, _ = await _find_integration_for_repo(repo)
    if not tenant_id:
        return

    from app.core.database import AsyncSessionLocal
    from app.models.vulnerability import Vulnerability
    from app.integrations.github.client import _map_severity, _first_fixed_version
    from sqlalchemy import select

    advisory = alert.get("security_advisory", {})
    pkg      = alert.get("dependency", {}).get("package", {}).get("name", "")
    cve_id   = advisory.get("cve_id")

    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Vulnerability).where(
                Vulnerability.tenant_id    == tenant_id,
                Vulnerability.target       == repo,
                Vulnerability.package_name == pkg,
            )
        )
        vuln = existing.scalar_one_or_none()

        if action in ("created",) and not vuln:
            db.add(Vulnerability(
                tenant_id      = tenant_id,
                cve_id         = cve_id,
                title          = advisory.get("summary", "Dependabot Alert")[:499],
                description    = advisory.get("description", ""),
                severity       = _map_severity(advisory.get("severity")),
                cvss_score     = advisory.get("cvss", {}).get("score"),
                status         = "open",
                package_name   = pkg,
                fixed_version  = _first_fixed_version(advisory),
                target         = repo,
                references     = [alert.get("html_url")] if alert.get("html_url") else [],
            ))
        elif action in ("fixed", "dismissed", "auto_dismissed") and vuln:
            vuln.status = "resolved"

        await db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _find_integration_for_repo(full_name: str) -> tuple[str | None, str | None]:
    """Find tenant_id + integration_id for a GitHub repo."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.integration import Integration
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Integration).where(
                    Integration.type      == "github",
                    Integration.is_active == True,
                    Integration.status    == "connected",
                )
            )
            for intg in result.scalars().all():
                repos = (intg.config or {}).get("repos", [])
                if not repos or full_name in repos:
                    return intg.tenant_id, intg.id
    except Exception as e:
        logger.error(f"_find_integration_for_repo error: {e}")
    return None, None


def _parse_dt(value: str | None):
    if not value:
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
