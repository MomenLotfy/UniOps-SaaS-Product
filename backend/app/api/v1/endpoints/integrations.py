from __future__ import annotations
"""
Integrations API — manage third-party service connections.

FIXES applied in this revision
────────────────────────────────
BUG #2 — update_integration() auto-sync block silently never ran.
  The condition checked `data.type` and `data.tenant_id`, but IntegrationUpdate
  has NEITHER of those fields.  Python raises AttributeError which was swallowed
  by the `# type: ignore` comments, meaning the `_bg_sync_repos` background
  task was never scheduled after a token update.

  Fix: read `integration.type` from the *response object* (which comes from the
  DB record and always has the type), and read `tenant_id` from the already-
  resolved FastAPI dependency — not from the request body.

BUG #3 — create_integration() committed and then the background task opened a
  NEW session and called test_connection() + sync_repos_for_tenant(). The new
  session could see the committed row, but the background task for git providers
  only ran sync_repos_for_tenant() when test succeeded.  This was actually fine
  but the auto-sync after update was completely dead (see BUG #2).
"""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query, status, HTTPException

from app.api.deps import AdminUser, CurrentUser, DBSession, TenantID
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.integration import (
    IntegrationCreate,
    IntegrationResponse,
    IntegrationTestResult,
    IntegrationUpdate,
)
from app.services.integration_service import IntegrationService
from app.utils.logger import logger

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# List / Get
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=APIResponse[PaginatedResponse])
async def list_integrations(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type_filter: Optional[str] = Query(None, alias="type"),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    svc = IntegrationService(db)
    result = await svc.list(tenant_id, page, page_size, type_filter, status_filter)
    return APIResponse(data=result)


@router.get("/{integration_id}", response_model=APIResponse[IntegrationResponse])
async def get_integration(
    integration_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    svc = IntegrationService(db)
    item = await svc.get_by_id(integration_id)
    return APIResponse(data=item)


# ─────────────────────────────────────────────────────────────────────────────
# Create
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", response_model=APIResponse[IntegrationResponse], status_code=status.HTTP_201_CREATED)
async def create_integration(
    data: IntegrationCreate,
    current_user: AdminUser,
    tenant_id: TenantID,
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    svc = IntegrationService(db)
    item = await svc.create(tenant_id, data)
    await db.commit()

    # Auto-test connection after creation (non-blocking)
    background_tasks.add_task(
        _bg_test_and_sync,
        integration_id=item.id,
        integration_type=data.type,
        tenant_id=tenant_id,
    )
    return APIResponse(data=item, message="Integration created — testing connection in background")


# ─────────────────────────────────────────────────────────────────────────────
# Shortcut: POST /integrations/aws
# Frontend AWSConnectModal sends flat payload — we normalise it here.
# MUST be declared BEFORE /{integration_id} routes so "aws" isn't captured
# as an integration_id → 405 Method Not Allowed.
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/aws", response_model=APIResponse[IntegrationResponse], status_code=status.HTTP_201_CREATED)
async def connect_aws(
    payload: dict,
    current_user: AdminUser,
    tenant_id: TenantID,
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    """Accept flat AWS form: {access_key_id, secret_access_key, region?, name?}"""
    from app.schemas.integration import IntegrationCreate as IC, IntegrationUpdate as IU
    from sqlalchemy import select as _sel
    from app.models.integration import Integration as _Intg

    access_key = payload.get("access_key_id") or payload.get("accessKeyId", "")
    secret_key = payload.get("secret_access_key") or payload.get("secretAccessKey", "")
    region     = payload.get("region", "us-east-1")
    name       = payload.get("name", "AWS Production")

    if not access_key or not secret_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="access_key_id and secret_access_key are required",
        )

    svc = IntegrationService(db)
    # Upsert: update existing AWS integration if one exists
    existing = (await db.execute(
        _sel(_Intg).where(_Intg.tenant_id == tenant_id, _Intg.type == "aws")
    )).scalar_one_or_none()

    if existing:
        item = await svc.update(existing.id, IU(
            name=name, is_active=True,
            credentials={"access_key_id": access_key, "secret_access_key": secret_key},
            config={"region": region},
        ))
        await db.commit()
        bg_id = existing.id
    else:
        item = await svc.create(tenant_id, IC(
            name=name, type="aws",
            credentials={"access_key_id": access_key, "secret_access_key": secret_key},
            config={"region": region},
        ))
        await db.commit()
        bg_id = item.id

    background_tasks.add_task(_bg_test_and_sync, integration_id=bg_id,
                               integration_type="aws", tenant_id=tenant_id)
    return APIResponse(data=item, message="AWS integration saved — testing credentials in background")


@router.post("/kubernetes", response_model=APIResponse[IntegrationResponse], status_code=status.HTTP_201_CREATED)
async def connect_kubernetes(
    payload: dict,
    current_user: AdminUser,
    tenant_id: TenantID,
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    """Accept flat K8s form: {kubeconfig, context?, clusterName?}"""
    from app.schemas.integration import IntegrationCreate as IC

    kubeconfig   = payload.get("kubeconfig", "").strip()
    cluster_name = payload.get("clusterName") or payload.get("cluster_name", "Kubernetes Cluster")
    ctx          = payload.get("context", "")

    if not kubeconfig:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="kubeconfig is required",
        )

    svc  = IntegrationService(db)
    item = await svc.create(tenant_id, IC(
        name=cluster_name, type="kubernetes",
        credentials={"kubeconfig": kubeconfig},
        config={"context": ctx} if ctx else {},
    ))
    await db.commit()
    background_tasks.add_task(_bg_test_and_sync, integration_id=item.id,
                               integration_type="kubernetes", tenant_id=tenant_id)
    return APIResponse(data=item, message="Kubernetes integration saved — testing connection in background")


# ─────────────────────────────────────────────────────────────────────────────
# Update / Patch
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/{integration_id}", response_model=APIResponse[IntegrationResponse])
async def update_integration(
    integration_id: str,
    data: IntegrationUpdate,
    current_user: AdminUser,
    tenant_id: TenantID,       # ← FIX #2a: resolve tenant from JWT, not from request body
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    svc = IntegrationService(db)
    item = await svc.update(integration_id, data)
    await db.commit()

    # ── FIX #2b ───────────────────────────────────────────────────────────────
    # OLD (broken): `data.type` → AttributeError (not in IntegrationUpdate)
    #               `data.tenant_id` → AttributeError (not in IntegrationUpdate)
    # Both were silently ignored via `# type: ignore`, so bg sync NEVER ran.
    #
    # NEW (correct): read `type` from the DB response object (`item.type`) and
    # `tenant_id` from the already-resolved FastAPI dependency above.
    # We also accept status="testing" (set by frontend during connect flow) so
    # the background test fires immediately after token save — not only after
    # the explicit test endpoint is called.
    # ─────────────────────────────────────────────────────────────────────────
    integration_type = item.type
    if integration_type in ("github", "gitlab", "aws"):
        # Re-test + sync when credentials are updated for git OR cloud integrations.
        # For AWS: re-tests credentials and immediately syncs costs on success.
        background_tasks.add_task(
            _bg_test_and_sync,
            integration_id=integration_id,
            integration_type=integration_type,
            tenant_id=tenant_id,
        )

    return APIResponse(data=item)


# PATCH is semantically identical to PUT for partial updates
@router.patch("/{integration_id}", response_model=APIResponse[IntegrationResponse])
async def patch_integration(
    integration_id: str,
    data: IntegrationUpdate,
    current_user: AdminUser,
    tenant_id: TenantID,
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    return await update_integration(integration_id, data, current_user, tenant_id, db, background_tasks)


# ─────────────────────────────────────────────────────────────────────────────
# Delete
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{integration_id}", status_code=status.HTTP_200_OK)
async def delete_integration(
    integration_id: str,
    current_user: AdminUser,
    db: DBSession,
):
    svc = IntegrationService(db)
    await svc.delete(integration_id)
    await db.commit()
    return APIResponse(message="Integration disconnected")


# ─────────────────────────────────────────────────────────────────────────────
# Test / Sync
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{integration_id}/test", response_model=APIResponse[IntegrationTestResult])
async def test_integration(
    integration_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    svc = IntegrationService(db)
    result = await svc.test_connection(integration_id)
    await db.commit()
    return APIResponse(data=result)


@router.post("/{integration_id}/sync")
async def sync_integration(
    integration_id: str,
    current_user: AdminUser,
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    """Trigger a manual sync — runs in background, returns immediately."""
    svc = IntegrationService(db)
    integration = await svc.get_by_id(integration_id)

    if integration.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="integration_not_ready",
        )

    background_tasks.add_task(
        _bg_sync,
        integration_id=integration_id,
        integration_type=integration.type,
    )
    return APIResponse(
        data={"integration_id": integration_id, "status": "syncing"},
        message="Sync started in background",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Background task helpers (no business logic — just orchestrate service calls)
# ─────────────────────────────────────────────────────────────────────────────

async def _bg_test_and_sync(
    integration_id: str,
    integration_type: str,
    tenant_id: str,
) -> None:
    """
    Background: test connection, then sync data for the provider type.
    Uses its own DB session (BackgroundTask runs after response is sent).
    """
    try:
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            svc = IntegrationService(db)
            result = await svc.test_connection(integration_id)
            await db.commit()

            if result.success and integration_type in ("github", "gitlab"):
                sync_result = await svc.sync_repos_for_tenant(tenant_id)
                await db.commit()
                logger.info(
                    f"[bg] Connection test OK + synced {sync_result['synced']} repos "
                    f"for integration {integration_id} (tenant {tenant_id})"
                )
                # Also pull CI/CD pipeline runs so DevOps Center shows data immediately
                try:
                    from app.tasks.sync_pipelines import _sync_pipelines
                    pipe_result = await _sync_pipelines(tenant_id=tenant_id)
                    logger.info(
                        f"[bg] Initial pipeline sync: {pipe_result['pipelines']} runs "
                        f"for integration {integration_id}"
                    )
                except Exception as pipe_exc:
                    logger.warning(f"[bg] Initial pipeline sync failed (non-fatal): {pipe_exc}")
            elif result.success and integration_type == "aws":
                # Trigger AWS cost sync immediately after a successful connection test
                # so cost data appears without waiting for the hourly beat schedule.
                logger.info(f"[bg] AWS connection OK — triggering cost sync for tenant {tenant_id}")
                try:
                    from app.tasks.sync_costs import sync_aws_costs_async
                    await sync_aws_costs_async(tenant_id=tenant_id)
                    logger.info(f"[bg] AWS cost sync completed for tenant {tenant_id}")
                except Exception as sync_exc:
                    logger.warning(f"[bg] AWS cost sync failed (non-fatal): {sync_exc}")
            elif not result.success:
                logger.warning(
                    f"[bg] Connection test FAILED for {integration_id}: {result.message}"
                )
    except Exception as exc:
        logger.error(f"[bg] _bg_test_and_sync failed for {integration_id}: {exc}")


async def _bg_sync(integration_id: str, integration_type: str) -> None:
    """Background: run integration sync."""
    try:
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            svc = IntegrationService(db)
            result = await svc.sync(integration_id)
            await db.commit()
            logger.info(f"[bg] Sync complete for integration {integration_id}: {result}")

        # Resolve tenant_id once — used by both AWS and GitHub branches below.
        if integration_type in ("aws", "github", "gitlab"):
            try:
                from app.models.integration import Integration as _Intg
                from sqlalchemy import select as _sel

                async with AsyncSessionLocal() as db2:
                    row = (await db2.execute(
                        _sel(_Intg).where(_Intg.id == integration_id)
                    )).scalar_one_or_none()
                    tenant_id = row.tenant_id if row else None
            except Exception:
                tenant_id = None
        else:
            tenant_id = None

        # For AWS: persist cost data via sync_aws_costs_async (svc.sync() only
        # updates metadata, not the CostMetric rows that the UI reads).
        if integration_type == "aws" and tenant_id:
            try:
                from app.tasks.sync_costs import sync_aws_costs_async
                await sync_aws_costs_async(tenant_id=tenant_id)
                logger.info(f"[bg] AWS cost sync completed for integration {integration_id}")
            except Exception as cost_exc:
                logger.warning(f"[bg] AWS cost sync failed (non-fatal): {cost_exc}")

        # For GitHub/GitLab: trigger full pipeline sync so "Sync Now" in the UI
        # actually pulls fresh CI/CD runs (not just repo metadata).
        if integration_type in ("github", "gitlab") and tenant_id:
            try:
                from app.tasks.sync_pipelines import _sync_pipelines
                pipeline_result = await _sync_pipelines(tenant_id=tenant_id)
                logger.info(f"[bg] Pipeline sync completed for integration {integration_id}: {pipeline_result}")
            except Exception as pipe_exc:
                logger.warning(f"[bg] Pipeline sync failed (non-fatal): {pipe_exc}")

    except Exception as exc:
        logger.error(f"[bg] _bg_sync failed for {integration_id}: {exc}")


async def _bg_sync_repos(tenant_id: str) -> None:
    """Background: re-sync all repos for a tenant after a new integration connects."""
    try:
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            svc = IntegrationService(db)
            sync_result = await svc.sync_repos_for_tenant(tenant_id)
            await db.commit()
            logger.info(
                f"[bg] Auto-sync repos: {sync_result['synced']} repos "
                f"for tenant {tenant_id}"
            )
    except Exception as exc:
        logger.error(f"[bg] _bg_sync_repos failed for tenant {tenant_id}: {exc}")
