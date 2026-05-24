from __future__ import annotations
"""Pipelines API — CI/CD pipeline management, re-run, and job inspection."""
from typing import Optional
from fastapi import APIRouter, Query, BackgroundTasks
from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession
from app.schemas.pipeline import PipelineResponse, PipelineStats, PipelineRerunResult, PipelineJob
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.pipeline_service import PipelineService

router = APIRouter()


@router.get("", response_model=APIResponse[PaginatedResponse])
async def list_pipelines(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    repository: Optional[str] = Query(None),
    branch: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    svc = PipelineService(db)
    result = await svc.list_pipelines(tenant_id, page, page_size, repository, branch, status)
    return APIResponse(data=result)


@router.get("/stats", response_model=APIResponse[PipelineStats])
async def get_pipeline_stats(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = PipelineService(db)
    stats = await svc.get_stats(tenant_id)
    return APIResponse(data=stats)


@router.get("/repositories")
async def list_repositories(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = PipelineService(db)
    repos = await svc.list_repositories(tenant_id)
    return APIResponse(data=repos)


@router.get("/{pipeline_id}", response_model=APIResponse[PipelineResponse])
async def get_pipeline(pipeline_id: str, current_user: CurrentUser, db: DBSession):
    svc = PipelineService(db)
    pipeline = await svc.get_by_id(pipeline_id)
    return APIResponse(data=pipeline)


@router.get("/{pipeline_id}/jobs", response_model=APIResponse[list[PipelineJob]])
async def get_pipeline_jobs(pipeline_id: str, current_user: CurrentUser, db: DBSession):
    """
    Fetch live job/step breakdown for a pipeline run.
    Calls the provider API in real-time (GitHub Actions jobs / GitLab pipeline jobs).
    """
    svc = PipelineService(db)
    jobs = await svc.get_jobs(pipeline_id)
    return APIResponse(data=jobs)


@router.post("/{pipeline_id}/rerun", response_model=APIResponse[PipelineRerunResult])
async def rerun_pipeline(
    pipeline_id: str,
    current_user: AdminUser,
    db: DBSession,
    failed_only: bool = Query(
        default=True,
        description="GitHub only: re-run failed jobs only (true) or all jobs (false). "
                    "GitLab always retries failed jobs.",
    ),
):
    """
    Re-run a pipeline on its provider.

    - **GitHub + failed_only=true** → `POST .../runs/{id}/rerun-failed-jobs`
    - **GitHub + failed_only=false** → `POST .../runs/{id}/rerun` (all jobs)
    - **GitLab** → `POST .../pipelines/{id}/retry`

    Guards: returns 422 if pipeline is already running/queued.
    Requires: admin or devops role.
    """
    svc = PipelineService(db)
    result = await svc.rerun(pipeline_id, current_user["user_id"], failed_only=failed_only)
    return APIResponse(data=result, message=result.message)


@router.post("/sync")
async def trigger_sync(
    current_user: AdminUser, tenant_id: TenantID,
    background_tasks: BackgroundTasks,
):
    """Manually trigger pipeline sync from GitHub/GitLab."""
    background_tasks.add_task(_background_sync, tenant_id)
    return APIResponse(data={"status": "syncing"}, message="Pipeline sync started in background")


async def _background_sync(tenant_id: str):
    try:
        from app.tasks.sync_pipelines import _sync_pipelines
        result = await _sync_pipelines(tenant_id)
        from app.utils.logger import logger
        logger.info(f"Pipeline sync done: {result}")
    except Exception as e:
        from app.utils.logger import logger
        logger.error(f"Background pipeline sync failed: {e}")

