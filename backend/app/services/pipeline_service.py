from __future__ import annotations
"""Pipeline service — CI/CD data, stats, and real provider re-run execution."""
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import Pipeline
from app.models.integration import Integration
from app.models.audit_log import AuditLog
from app.schemas.pipeline import PipelineResponse, PipelineStats, PipelineRerunResult, PipelineJob
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundError, IntegrationError, ValidationError
from app.services.base import BaseService
from app.utils.logger import logger

# Statuses that CAN be re-run
_RERUNNABLE = {"failed", "cancelled", "canceled", "error", "timed_out", "skipped"}
# Statuses that should NOT be re-run (already active)
_ACTIVE = {"running", "queued", "pending", "in_progress", "waiting"}


def _decrypt_creds(credentials: dict) -> dict:
    from app.utils.encryption import decrypt
    result = {}
    for k, v in (credentials or {}).items():
        try:
            result[k] = decrypt(v)
        except Exception:
            result[k] = v
    return result


class PipelineService(BaseService):

    # ── Read operations ───────────────────────────────────────────────────────

    async def list_pipelines(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        repository: Optional[str] = None,
        branch: Optional[str] = None,
        status: Optional[str] = None,
    ) -> PaginatedResponse:
        query = select(Pipeline).where(Pipeline.tenant_id == tenant_id)
        if repository:
            query = query.where(Pipeline.repository.ilike(f"%{repository}%"))
        if branch:
            query = query.where(Pipeline.branch == branch)
        if status:
            query = query.where(Pipeline.status == status)

        total = await self._count(query)
        query = query.order_by(Pipeline.created_at.desc())
        items = await self._paginate(query, page, page_size)
        return PaginatedResponse(
            data=[PipelineResponse.model_validate(p) for p in items],
            total=total, page=page, page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def get_by_id(self, pipeline_id: str) -> PipelineResponse:
        pipeline = await self._get_by_id(Pipeline, pipeline_id)
        return PipelineResponse.model_validate(pipeline)

    async def get_stats(self, tenant_id: str, days: int = 30) -> PipelineStats:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(Pipeline).where(
                Pipeline.tenant_id == tenant_id,
                Pipeline.created_at >= since,
            )
        )
        pipelines = result.scalars().all()
        total   = len(pipelines)
        running = sum(1 for p in pipelines if p.status in _ACTIVE)
        success = sum(1 for p in pipelines if p.status in ("success", "passed"))
        failed  = sum(1 for p in pipelines if p.status in ("failed", "error"))
        durations = [p.duration for p in pipelines if p.duration]
        return PipelineStats(
            total=total,
            running=running,
            success=success,
            failed=failed,
            success_rate=round(success / total * 100, 1) if total else 0.0,
            avg_duration_seconds=round(sum(durations) / len(durations), 1) if durations else 0.0,
        )

    async def list_repositories(self, tenant_id: str) -> list[str]:
        result = await self.db.execute(
            select(Pipeline.repository)
            .where(Pipeline.tenant_id == tenant_id)
            .distinct()
            .order_by(Pipeline.repository)
        )
        return [r[0] for r in result.fetchall() if r[0]]

    async def get_jobs(self, pipeline_id: str) -> list[PipelineJob]:
        """Fetch live job/step list for a pipeline from the provider."""
        pipeline, integration = await self._resolve(pipeline_id)
        creds  = _decrypt_creds(integration.credentials)
        config = {**creds, **(integration.config or {})}

        if integration.type == "github":
            return await self._github_get_jobs(pipeline, config)
        elif integration.type == "gitlab":
            return await self._gitlab_get_jobs(pipeline, config)
        return []

    # ── Re-run operation ──────────────────────────────────────────────────────

    async def rerun(
        self,
        pipeline_id: str,
        triggered_by: str,
        failed_only: bool = False,
    ) -> PipelineRerunResult:
        """
        Re-run a pipeline on its provider (GitHub or GitLab).

        - GitHub + failed_only=False  → rerun all jobs
        - GitHub + failed_only=True   → rerun failed jobs only (faster, cheaper)
        - GitLab                      → retry pipeline (always equivalent to failed_only)

        Guards:
        - Raises ValidationError if pipeline is already running/queued
        - Raises IntegrationError if provider call fails
        - Writes AuditLog on success
        """
        pipeline, integration = await self._resolve(pipeline_id)

        # ── Guard: don't re-run an already-active pipeline ──────────────────
        if pipeline.status.lower() in _ACTIVE:
            raise ValidationError(
                f"Pipeline is already {pipeline.status} — cannot re-run",
                field="status",
            )

        creds  = _decrypt_creds(integration.credentials)
        config = {**creds, **(integration.config or {})}

        # ── Dispatch to provider ─────────────────────────────────────────────
        if integration.type == "github":
            result = await self._github_rerun(pipeline, config, failed_only)
        elif integration.type == "gitlab":
            result = await self._gitlab_retry(pipeline, config)
        else:
            raise IntegrationError(
                integration.type,
                f"Re-run not supported for provider '{integration.type}'",
            )

        if not result["success"]:
            raise IntegrationError(
                integration.type,
                result.get("error", "Re-run failed"),
            )

        # ── Update DB state ──────────────────────────────────────────────────
        pipeline.status       = "queued"
        pipeline.triggered_by = triggered_by
        pipeline.started_at   = None
        pipeline.finished_at  = None
        pipeline.duration     = None
        pipeline.updated_at   = datetime.now(timezone.utc)

        new_run_id = result.get("new_run_id") or result.get("run_id")
        if new_run_id and str(new_run_id) != pipeline.external_id:
            # GitLab creates a NEW pipeline — update external_id and logs_url
            pipeline.external_id = str(new_run_id)
            if result.get("web_url"):
                pipeline.logs_url = result["web_url"]

        # ── Audit log ────────────────────────────────────────────────────────
        action = (
            "pipeline.rerun_failed" if failed_only and integration.type == "github"
            else "pipeline.rerun"
        )
        await self._write_audit(
            tenant_id  = pipeline.tenant_id,
            user_id    = triggered_by,
            action     = action,
            resource   = "pipeline",
            resource_id= pipeline_id,
            details    = {
                "name":         pipeline.name,
                "repository":   pipeline.repository,
                "branch":       pipeline.branch,
                "external_id":  pipeline.external_id,
                "provider":     integration.type,
                "failed_only":  failed_only,
            },
        )
        await self.db.flush()

        action_label = (
            "rerun_failed" if failed_only and integration.type == "github"
            else ("retry"  if integration.type == "gitlab" else "rerun_all")
        )
        logger.info(
            f"[audit] {action} {pipeline.repository}#{pipeline.branch} "
            f"run={pipeline.external_id} by={triggered_by}"
        )
        return PipelineRerunResult(
            success        = True,
            action         = action_label,
            pipeline_id    = pipeline_id,
            external_run_id= str(new_run_id) if new_run_id else pipeline.external_id,
            provider       = integration.type,
            message        = (
                f"{'Failed jobs re-run' if failed_only else 'Pipeline re-run'} queued "
                f"for '{pipeline.name}' on {pipeline.repository}"
            ),
            logs_url       = pipeline.logs_url,
        )

    # ── Provider helpers ──────────────────────────────────────────────────────

    async def _github_rerun(self, pipeline: Pipeline, config: dict, failed_only: bool) -> dict:
        from app.integrations.github.client import GitHubClient
        client = GitHubClient(config)

        repo = pipeline.repository or ""
        parts = repo.split("/", 1)
        if len(parts) != 2:
            return {"success": False, "error": f"Cannot parse owner/repo from '{repo}'"}
        owner, repo_name = parts

        run_id = pipeline.external_id
        if not run_id:
            return {"success": False, "error": "Pipeline has no external_id (GitHub run ID)"}

        if failed_only:
            return await client.rerun_failed_jobs(owner, repo_name, run_id)
        return await client.rerun_workflow_run(owner, repo_name, run_id)

    async def _gitlab_retry(self, pipeline: Pipeline, config: dict) -> dict:
        from app.integrations.gitlab.client import GitLabClient
        client = GitLabClient(config)

        project_id  = (pipeline.metadata_ or {}).get("project_id") or config.get("project_id")
        pipeline_id = pipeline.external_id

        if not project_id:
            return {"success": False, "error": "GitLab project_id not found in pipeline metadata or integration config"}
        if not pipeline_id:
            return {"success": False, "error": "Pipeline has no external_id (GitLab pipeline ID)"}

        return await client.retry_pipeline(str(project_id), str(pipeline_id))

    async def _github_get_jobs(self, pipeline: Pipeline, config: dict) -> list[PipelineJob]:
        from app.integrations.github.client import GitHubClient
        client = GitHubClient(config)
        repo   = pipeline.repository or ""
        parts  = repo.split("/", 1)
        if len(parts) != 2:
            return []
        owner, repo_name = parts
        raw_jobs = await client.get_run_jobs(owner, repo_name, int(pipeline.external_id))
        return [
            PipelineJob(
                id          = str(j["id"]),
                name        = j["name"],
                status      = j["status"],
                started_at  = _parse_dt(j.get("started_at")),
                finished_at = _parse_dt(j.get("completed_at")),
            )
            for j in raw_jobs
        ]

    async def _gitlab_get_jobs(self, pipeline: Pipeline, config: dict) -> list[PipelineJob]:
        from app.integrations.gitlab.client import GitLabClient
        client     = GitLabClient(config)
        project_id = (pipeline.metadata_ or {}).get("project_id") or config.get("project_id")
        if not project_id:
            return []
        raw_jobs = await client.get_pipeline_jobs(str(project_id), pipeline.external_id)
        return [PipelineJob(**j) for j in raw_jobs]

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _resolve(self, pipeline_id: str) -> tuple[Pipeline, Integration]:
        pipeline = await self._get_by_id(Pipeline, pipeline_id)
        if not pipeline.integration_id:
            raise IntegrationError("Pipeline", "No integration associated")
        integration = await self._get_or_none(Integration, pipeline.integration_id)
        if not integration:
            raise IntegrationError("Pipeline", "Integration record not found")
        if not integration.is_active or integration.status != "connected":
            raise IntegrationError(
                integration.type,
                f"Integration '{integration.name}' is not connected (status={integration.status})",
            )
        return pipeline, integration

    async def _write_audit(
        self, tenant_id: str, user_id: str, action: str,
        resource: str, resource_id: str, details: dict, status: str = "success",
    ) -> None:
        try:
            self.db.add(AuditLog(
                tenant_id=tenant_id, user_id=user_id, action=action,
                resource=resource, resource_id=resource_id,
                details=details, status=status,
            ))
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Audit log write failed (non-fatal): {e}")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None



class PipelineService(BaseService):
    async def list(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        repository: Optional[str] = None,
        integration_id: Optional[str] = None,
    ) -> PaginatedResponse:
        query = select(Pipeline).where(Pipeline.tenant_id == tenant_id)
        if status:
            query = query.where(Pipeline.status == status)
        if repository:
            query = query.where(Pipeline.repository.ilike(f"%{repository}%"))
        if integration_id:
            query = query.where(Pipeline.integration_id == integration_id)

        total = await self._count(query)
        query = query.order_by(Pipeline.created_at.desc())
        items = await self._paginate(query, page, page_size)

        return PaginatedResponse(
            data=[PipelineResponse.model_validate(i) for i in items],
            total=total, page=page, page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def get_by_id(self, pipeline_id: str) -> PipelineResponse:
        pipeline = await self._get_by_id(Pipeline, pipeline_id)
        return PipelineResponse.model_validate(pipeline)

    async def get_stats(self, tenant_id: str, days: int = 30) -> PipelineStats:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        query = select(Pipeline).where(
            Pipeline.tenant_id == tenant_id,
            Pipeline.created_at >= since,
        )
        result = await self.db.execute(query)
        pipelines = result.scalars().all()

        total = len(pipelines)
        running = sum(1 for p in pipelines if p.status == "running")
        success = sum(1 for p in pipelines if p.status in ("success", "passed"))
        failed = sum(1 for p in pipelines if p.status in ("failed", "error"))

        success_rate = (success / total * 100) if total > 0 else 0.0

        durations = [p.duration for p in pipelines if p.duration]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        return PipelineStats(
            total=total,
            running=running,
            success=success,
            failed=failed,
            success_rate=round(success_rate, 1),
            avg_duration_seconds=round(avg_duration, 1),
        )

    async def retry(self, pipeline_id: str, triggered_by: str) -> dict:
        pipeline = await self._get_by_id(Pipeline, pipeline_id)
        if not pipeline.integration_id:
            return {"message": "No integration associated with this pipeline", "success": False}

        integration = await self._get_or_none(Integration, pipeline.integration_id)
        if not integration:
            return {"message": "Integration not found", "success": False}

        pipeline.status = "pending"
        pipeline.triggered_by = triggered_by
        pipeline.started_at = None
        pipeline.finished_at = None
        await self.db.flush()

        return {"message": "Pipeline retry initiated", "success": True, "pipeline_id": pipeline_id}

    async def get_recent_by_repo(self, tenant_id: str, repository: str, limit: int = 10) -> list[PipelineResponse]:
        query = (
            select(Pipeline)
            .where(Pipeline.tenant_id == tenant_id, Pipeline.repository == repository)
            .order_by(Pipeline.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return [PipelineResponse.model_validate(p) for p in result.scalars().all()]

    async def list_pipelines(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        repository: Optional[str] = None,
        branch: Optional[str] = None,
        status: Optional[str] = None,
    ) -> PaginatedResponse:
        query = select(Pipeline).where(Pipeline.tenant_id == tenant_id)
        if repository:
            query = query.where(Pipeline.repository.ilike(f"%{repository}%"))
        if branch:
            query = query.where(Pipeline.branch == branch)
        if status:
            query = query.where(Pipeline.status == status)

        total = await self._count(query)
        query = query.order_by(Pipeline.created_at.desc())
        items = await self._paginate(query, page, page_size)
        return PaginatedResponse(
            data=[PipelineResponse.model_validate(p) for p in items],
            total=total, page=page, page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def list_repositories(self, tenant_id: str) -> list[str]:
        result = await self.db.execute(
            select(Pipeline.repository)
            .where(Pipeline.tenant_id == tenant_id)
            .distinct()
            .order_by(Pipeline.repository)
        )
        return [r[0] for r in result.fetchall() if r[0]]
