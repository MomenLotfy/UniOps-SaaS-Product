"""
DeploymentEngine — the core brain of the UniOps Platform Engineering layer (Epic 7).

Pipeline executed on service.create():
  1. Validate request
  2. Persist service record (status=Creating)
  3. Generate Git repository
  4. Push project scaffold + Dockerfile
  5. Push CI/CD pipeline (GitHub Actions / GitLab CI)
  6. Push Helm chart
  7. Push ArgoCD Application manifest
  8. Register ArgoCD Application via API (if ArgoCD integration configured)
  9. Trigger ArgoCD sync
 10. Start background tracking task
 11. Emit WebSocket events at every stage

All stages are wrapped in try/except so failures are graceful:
  - DB record is updated to status=Failed
  - service.failed WebSocket event is emitted
  - Step is logged to deployment_logs
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.websocket.manager import ws_manager
from app.core.deployment_engine.argocd import get_argocd_client
from app.core.deployment_engine.generators import (
    generate_argocd_manifest,
    generate_dockerfile,
    generate_github_actions,
    generate_gitlab_ci,
    generate_helm_chart,
)
from app.core.deployment_engine.git_provider import get_provider_from_integration
from app.models.deployment_log import DeploymentLog
from app.models.integration import Integration
from app.models.service import CatalogService

logger = logging.getLogger(__name__)


# ── Payload schema (dict-based — avoids circular imports with Pydantic) ────────

class ServiceCreatePayload:
    def __init__(self, data: dict):
        self.name        = data["name"]
        self.type        = data.get("type", "Microservice")
        self.tech_stack  = data.get("tech_stack", "Other")
        self.description = data.get("description", "")
        self.git_repo    = data.get("git_repo", "")       # desired repo name / URL
        self.cluster     = data.get("cluster", "")
        self.namespace   = data.get("namespace", "default")
        self.replicas    = int(data.get("replicas", 1))
        self.owner       = data.get("owner", "")
        self.tags        = data.get("tags", [])


# ── Main engine ───────────────────────────────────────────────────────────────

class DeploymentEngine:
    """
    Orchestrates the end-to-end deployment pipeline for a new catalog service.
    Instantiated per-request; the DB session is passed in from the API layer.
    """

    def __init__(self, db: AsyncSession, tenant_id: str, user_id: str = ""):
        self.db        = db
        self.tenant_id = tenant_id
        self.user_id   = user_id

    # ── Public entry point ────────────────────────────────────────────────────

    async def create_service(self, payload: ServiceCreatePayload) -> CatalogService:
        """
        Main orchestration method.  Returns the CatalogService record (may have
        status=Failed if an early step failed).
        """
        svc = await self._persist_service(payload)
        asyncio.create_task(
            self._run_pipeline(svc, payload),
            name=f"deploy-{svc.id}",
        )
        return svc

    # ── Pipeline stages ───────────────────────────────────────────────────────

    async def _run_pipeline(self, svc: CatalogService, payload: ServiceCreatePayload) -> None:
        """
        Full async pipeline.  Each stage calls emit_event() and logs to DB.
        Failures update the service status and stop the pipeline.
        """
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            try:
                await self._stage_create_repo(db, svc, payload)
                await self._stage_push_scaffold(db, svc, payload)
                await self._stage_push_cicd(db, svc, payload)
                await self._stage_push_helm(db, svc, payload)
                await self._stage_register_gitops(db, svc, payload)
                await self._stage_trigger_sync(db, svc)
                await self._stage_finalize(db, svc)
            except _PipelineAbort as abort:
                await self._fail_service(db, svc, str(abort))
            except Exception as exc:
                logger.exception(f"[engine] Unhandled error for service {svc.id}: {exc}")
                await self._fail_service(db, svc, f"Unexpected error: {exc}")

    # ── Stage implementations ─────────────────────────────────────────────────

    async def _stage_create_repo(
        self, db: AsyncSession, svc: CatalogService, payload: ServiceCreatePayload
    ) -> None:
        await self.emit_event("service.building", svc, {"step": "create_repo"})
        await self._update_status(db, svc, "Building")
        t0 = time.monotonic()

        git_integration = await self._get_git_integration(db)
        provider        = get_provider_from_integration(
            git_integration.to_dict() if git_integration else {}
        ) if git_integration else None

        repo_url = ""
        if provider is None:
            # No Git integration — generate a placeholder repo URL and continue
            logger.warning(f"[engine:{svc.name}] No Git integration configured; skipping repo creation")
            repo_url = f"https://github.com/uniops-org/{svc.name}"
            await self._log(db, svc, "create_repo", "skipped", "No Git integration — placeholder URL assigned")
        else:
            # GitHub path
            from app.core.deployment_engine.git_provider import GitHubProvider, GitLabProvider

            if isinstance(provider, GitHubProvider):
                owner = await provider.get_authenticated_user() or "uniops-org"
                repo_name = svc.name
                if not await provider.repo_exists(owner, repo_name):
                    result = await provider.create_repo(repo_name, description=payload.description or f"UniOps managed: {repo_name}")
                    if result:
                        repo_url  = result.get("html_url", f"https://github.com/{owner}/{repo_name}")
                        svc._gh_owner = owner  # type: ignore[attr-defined]
                        svc._gh_repo  = repo_name  # type: ignore[attr-defined]
                    else:
                        # Non-fatal: continue with placeholder
                        repo_url = f"https://github.com/{owner}/{repo_name}"
                        logger.warning(f"[engine:{svc.name}] Repo creation failed; using placeholder URL")
                else:
                    repo_url = f"https://github.com/{owner}/{repo_name}"
                svc._gh_owner = owner    # type: ignore[attr-defined]
                svc._gh_repo  = repo_name  # type: ignore[attr-defined]
                await self._log(db, svc, "create_repo", "success", f"GitHub repo: {repo_url}", time.monotonic() - t0)

            elif isinstance(provider, GitLabProvider):
                result = await provider.create_repo(svc.name, description=payload.description or "")
                if result:
                    repo_url     = result.get("http_url_to_repo", "")
                    svc._gl_id   = result.get("id")  # type: ignore[attr-defined]
                else:
                    repo_url = f"https://gitlab.com/uniops-org/{svc.name}"
                await self._log(db, svc, "create_repo", "success", f"GitLab repo: {repo_url}", time.monotonic() - t0)

        svc.repo_url = repo_url
        await db.execute(
            __import__("sqlalchemy", fromlist=["update"]).update(CatalogService)
            .where(CatalogService.id == svc.id)
            .values(repo_url=repo_url)
        )
        await db.commit()
        await self.emit_event("service.repo_created", svc, {"repo_url": repo_url})

    async def _stage_push_scaffold(
        self, db: AsyncSession, svc: CatalogService, payload: ServiceCreatePayload
    ) -> None:
        t0 = time.monotonic()
        dockerfile = generate_dockerfile(payload.tech_stack, payload.type)

        readme = (
            f"# {svc.name}\n\n"
            f"> Auto-generated by [UniOps Control Tower](https://uniops.app)\n\n"
            f"**Type:** {payload.type}  \n"
            f"**Stack:** {payload.tech_stack}  \n"
            f"**Cluster:** {payload.cluster}/{payload.namespace}  \n\n"
            f"This repository was scaffolded by the UniOps Self-Service Catalog.\n"
        )

        files = [
            (dockerfile.path, dockerfile.content),
            ("README.md",     readme),
        ]

        await self._push_files(db, svc, files, "chore: initial scaffold by UniOps")
        await self._log(db, svc, "push_scaffold", "success", f"Pushed {len(files)} files", time.monotonic() - t0)

    async def _stage_push_cicd(
        self, db: AsyncSession, svc: CatalogService, payload: ServiceCreatePayload
    ) -> None:
        t0 = time.monotonic()
        git_integration = await self._get_git_integration(db)
        provider_name   = (git_integration.type if git_integration else None) or "github"

        if "gitlab" in provider_name:
            ci_file = generate_gitlab_ci(svc.name, payload.tech_stack, payload.namespace)
        else:
            ci_file = generate_github_actions(svc.name, payload.tech_stack, payload.namespace, payload.cluster)

        await self._push_files(db, svc, [(ci_file.path, ci_file.content)], "ci: add CI/CD pipeline by UniOps")
        await self._log(db, svc, "push_cicd", "success", f"Pushed {ci_file.path}", time.monotonic() - t0)
        await self.emit_event("service.building", svc, {"step": "push_cicd", "file": ci_file.path})

    async def _stage_push_helm(
        self, db: AsyncSession, svc: CatalogService, payload: ServiceCreatePayload
    ) -> None:
        t0 = time.monotonic()
        helm_files   = generate_helm_chart(svc.name, payload.namespace, payload.replicas)
        helm_path    = f"helm/{svc.name}"
        svc.helm_chart_path = helm_path

        files = [(f.path, f.content) for f in helm_files]
        await self._push_files(db, svc, files, "feat: add Helm chart by UniOps")
        await db.execute(
            __import__("sqlalchemy", fromlist=["update"]).update(CatalogService)
            .where(CatalogService.id == svc.id)
            .values(helm_chart_path=helm_path)
        )
        await db.commit()
        await self._log(db, svc, "push_helm", "success", f"{len(files)} Helm files pushed", time.monotonic() - t0)
        await self.emit_event("service.building", svc, {"step": "push_helm", "path": helm_path})

    async def _stage_register_gitops(
        self, db: AsyncSession, svc: CatalogService, payload: ServiceCreatePayload
    ) -> None:
        t0       = time.monotonic()
        app_name = f"{svc.name}-{svc.namespace}"
        repo_url = svc.repo_url or f"https://github.com/uniops-org/{svc.name}"
        helm_path = svc.helm_chart_path or f"helm/{svc.name}"

        # 1. Push ArgoCD manifest to repo
        manifest = generate_argocd_manifest(
            app_name=app_name,
            repo_url=repo_url,
            helm_path=helm_path,
            namespace=payload.namespace,
        )
        await self._push_files(db, svc, [(manifest.path, manifest.content)], "feat: add ArgoCD application by UniOps")

        # 2. Register via ArgoCD API if integration is configured
        argocd_integration = await self._get_argocd_integration(db)
        client = get_argocd_client(argocd_integration.to_dict() if argocd_integration else {})

        if client:
            result = await client.create_application(
                app_name=app_name,
                repo_url=repo_url,
                helm_path=helm_path,
                namespace=payload.namespace,
            )
            status = "success" if result else "skipped (argocd API call failed)"
        else:
            status = "skipped (no argocd integration)"
            logger.info(f"[engine:{svc.name}] No ArgoCD integration configured; manifest pushed to repo only")

        svc.gitops_app_name = app_name
        await db.execute(
            __import__("sqlalchemy", fromlist=["update"]).update(CatalogService)
            .where(CatalogService.id == svc.id)
            .values(gitops_app_name=app_name)
        )
        await db.commit()
        await self._log(db, svc, "register_gitops", status, f"app_name={app_name}", time.monotonic() - t0)
        await self.emit_event("service.deploying", svc, {"step": "register_gitops", "app": app_name})

    async def _stage_trigger_sync(self, db: AsyncSession, svc: CatalogService) -> None:
        t0 = time.monotonic()
        argocd_integration = await self._get_argocd_integration(db)
        client = get_argocd_client(argocd_integration.to_dict() if argocd_integration else {})

        if client and svc.gitops_app_name:
            ok = await client.sync_application(svc.gitops_app_name)
            msg = "sync triggered" if ok else "sync trigger failed (non-fatal)"
        else:
            msg = "skipped (no argocd client)"

        await self._log(db, svc, "trigger_sync", "success", msg, time.monotonic() - t0)
        await self.emit_event("service.deploying", svc, {"step": "trigger_sync", "message": msg})

    async def _stage_finalize(self, db: AsyncSession, svc: CatalogService) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            __import__("sqlalchemy", fromlist=["update"]).update(CatalogService)
            .where(CatalogService.id == svc.id)
            .values(status="Deploying", last_deployment=now)
        )
        await db.commit()
        svc.status = "Deploying"
        await self.emit_event("service.deployed", svc, {"timestamp": now})

        # Start background tracker
        asyncio.create_task(
            self._track_deployment(svc.id, svc.gitops_app_name or ""),
            name=f"track-{svc.id}",
        )

    # ── Deployment status tracker ─────────────────────────────────────────────

    async def _track_deployment(self, service_id: str, app_name: str, max_polls: int = 30) -> None:
        """
        Polls ArgoCD every 10s to track deployment health.
        Updates service status in DB and emits WebSocket events.
        """
        from app.core.database import AsyncSessionLocal

        await asyncio.sleep(15)   # give the deployment time to start

        async with AsyncSessionLocal() as db:
            for attempt in range(max_polls):
                await asyncio.sleep(10)
                try:
                    # Fetch service
                    result = await db.execute(select(CatalogService).where(CatalogService.id == service_id))
                    svc = result.scalar_one_or_none()
                    if not svc:
                        break

                    argocd_integration = await self._get_argocd_integration_in_session(db, svc.tenant_id)
                    client = get_argocd_client(argocd_integration.to_dict() if argocd_integration else {})

                    if client and app_name:
                        health = await client.get_health_status(app_name)
                        sync   = await client.get_sync_status(app_name)

                        new_status = _argocd_health_to_service_status(health)
                        await db.execute(
                            __import__("sqlalchemy", fromlist=["update"]).update(CatalogService)
                            .where(CatalogService.id == service_id)
                            .values(status=new_status)
                        )
                        await db.commit()

                        await ws_manager.send_to_tenant(svc.tenant_id, {
                            "type": "service.synced",
                            "data": {
                                "service_id":   service_id,
                                "service_name": svc.name,
                                "health":       health,
                                "sync_status":  sync,
                                "status":       new_status,
                            },
                        })
                        logger.info(f"[tracker:{svc.name}] health={health} sync={sync} → {new_status}")

                        if health in ("Healthy",):
                            logger.info(f"[tracker:{svc.name}] Deployment successful. Stopping tracker.")
                            break
                        if health in ("Degraded",) and attempt >= 5:
                            await self._fail_service(db, svc, f"ArgoCD health={health}")
                            break
                    else:
                        # No ArgoCD — just mark Running after a delay
                        await db.execute(
                            __import__("sqlalchemy", fromlist=["update"]).update(CatalogService)
                            .where(CatalogService.id == service_id)
                            .values(status="Running")
                        )
                        await db.commit()
                        await ws_manager.send_to_tenant(svc.tenant_id, {
                            "type": "service.synced",
                            "data": {"service_id": service_id, "status": "Running"},
                        })
                        break

                except Exception as exc:
                    logger.warning(f"[tracker:{service_id}] poll error: {exc}")

    # ── WebSocket event emitter ───────────────────────────────────────────────

    async def emit_event(self, event_type: str, svc: CatalogService, extra: dict | None = None) -> None:
        payload: dict = {
            "type": event_type,
            "data": {
                "service_id":   svc.id,
                "service_name": svc.name,
                "service_type": svc.type,
                "status":       svc.status,
                "cluster":      svc.cluster,
                "namespace":    svc.namespace,
                **(extra or {}),
            },
        }
        await ws_manager.send_to_tenant(self.tenant_id, payload)
        logger.debug(f"[engine] emitted {event_type} for {svc.name}")

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _persist_service(self, payload: ServiceCreatePayload) -> CatalogService:
        svc = CatalogService(
            id          = str(uuid.uuid4()),
            tenant_id   = self.tenant_id,
            name        = payload.name,
            type        = payload.type,
            tech_stack  = payload.tech_stack,
            description = payload.description,
            owner       = payload.owner or self.user_id,
            cluster     = payload.cluster,
            namespace   = payload.namespace,
            replicas    = payload.replicas,
            status      = "Creating",
            tags        = payload.tags,
            git_provider= "github",
        )
        self.db.add(svc)
        await self.db.commit()
        await self.db.refresh(svc)
        await self.emit_event("service.created", svc, {})
        return svc

    async def _update_status(self, db: AsyncSession, svc: CatalogService, status: str) -> None:
        from sqlalchemy import update
        await db.execute(update(CatalogService).where(CatalogService.id == svc.id).values(status=status))
        await db.commit()
        svc.status = status

    async def _fail_service(self, db: AsyncSession, svc: CatalogService, reason: str) -> None:
        from sqlalchemy import update
        await db.execute(update(CatalogService).where(CatalogService.id == svc.id).values(status="Failed"))
        await db.commit()
        svc.status = "Failed"
        await ws_manager.send_to_tenant(svc.tenant_id, {
            "type": "service.failed",
            "data": {"service_id": svc.id, "service_name": svc.name, "reason": reason},
        })
        logger.error(f"[engine:{svc.name}] FAILED — {reason}")

    async def _log(
        self,
        db:       AsyncSession,
        svc:      CatalogService,
        step:     str,
        status:   str,
        message:  str,
        duration: float | None = None,
    ) -> None:
        entry = DeploymentLog(
            tenant_id    = self.tenant_id,
            service_id   = svc.id,
            service_name = svc.name,
            step         = step,
            status       = status,
            message      = message,
            duration_ms  = round(duration * 1000, 1) if duration else None,
        )
        db.add(entry)
        await db.commit()

    # ── Git file pusher ───────────────────────────────────────────────────────

    async def _push_files(
        self,
        db:      AsyncSession,
        svc:     CatalogService,
        files:   list[tuple[str, str]],
        message: str,
    ) -> None:
        """Push files to the service's git repo (no-op if no git integration)."""
        git_integration = await self._get_git_integration(db)
        provider        = get_provider_from_integration(
            git_integration.to_dict() if git_integration else {}
        ) if git_integration else None

        if provider is None:
            logger.info(f"[engine:{svc.name}] No git provider — skipping file push ({len(files)} files)")
            return

        from app.core.deployment_engine.git_provider import GitHubProvider, GitLabProvider

        if isinstance(provider, GitHubProvider):
            owner = getattr(svc, "_gh_owner", None) or await provider.get_authenticated_user() or "uniops-org"
            repo  = getattr(svc, "_gh_repo", None) or svc.name
            await provider.push_files_batch(owner, repo, files, message=message)

        elif isinstance(provider, GitLabProvider):
            project_id = getattr(svc, "_gl_id", None)
            if project_id:
                for path, content in files:
                    await provider.push_file(project_id, path, content, message)

    # ── Integration lookups ───────────────────────────────────────────────────

    async def _get_git_integration(self, db: AsyncSession) -> Optional[Integration]:
        result = await db.execute(
            select(Integration).where(
                Integration.tenant_id == self.tenant_id,
                Integration.type.in_(["github", "gitlab"]),
                Integration.status == "connected",
                Integration.is_active.is_(True),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_argocd_integration(self, db: AsyncSession) -> Optional[Integration]:
        result = await db.execute(
            select(Integration).where(
                Integration.tenant_id == self.tenant_id,
                Integration.type == "argocd",
                Integration.status == "connected",
                Integration.is_active.is_(True),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_argocd_integration_in_session(self, db: AsyncSession, tenant_id: str) -> Optional[Integration]:
        result = await db.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.type == "argocd",
                Integration.status == "connected",
            ).limit(1)
        )
        return result.scalar_one_or_none()


# ── Helpers ───────────────────────────────────────────────────────────────────

class _PipelineAbort(Exception):
    """Raised to abort the pipeline at a non-recoverable stage."""


def _argocd_health_to_service_status(health: str) -> str:
    return {
        "Healthy":     "Running",
        "Degraded":    "Failed",
        "Progressing": "Deploying",
        "Missing":     "Deploying",
        "Suspended":   "Stopped",
    }.get(health, "Deploying")
