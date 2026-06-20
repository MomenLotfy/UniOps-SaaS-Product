"""
Deployment Worker — startup background service (Epic 7).

Responsibilities:
  1. Resume in-flight deployments after a server restart
     (services stuck in Creating/Building/Deploying state)
  2. Periodic health checks for Running services with an ArgoCD app
  3. Emit WebSocket updates as status changes

Started as an asyncio task during FastAPI lifespan startup.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

logger = logging.getLogger(__name__)

_RESUME_DELAY_S    = 10     # Wait after startup before scanning stuck services
_HEALTH_INTERVAL_S = 120    # How often to re-poll healthy services
_STUCK_CUTOFF_S    = 300    # Services creating for >5 min are considered stuck


async def run_deployment_worker() -> None:
    """
    Long-running background coroutine.  Awaited via asyncio.create_task()
    in main.py lifespan startup.
    """
    logger.info("[deployment_worker] started")
    await asyncio.sleep(_RESUME_DELAY_S)

    while True:
        try:
            await _tick()
        except asyncio.CancelledError:
            logger.info("[deployment_worker] cancelled — shutting down")
            return
        except Exception as exc:
            logger.warning(f"[deployment_worker] tick error (non-fatal): {exc}")

        await asyncio.sleep(_HEALTH_INTERVAL_S)


async def _tick() -> None:
    """Single worker iteration."""
    from app.core.database import AsyncSessionLocal
    from app.models.service import CatalogService
    from app.api.v1.websocket.manager import ws_manager
    from app.core.deployment_engine.argocd import get_argocd_client
    from app.models.integration import Integration

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_STUCK_CUTOFF_S)

    async with AsyncSessionLocal() as db:
        # 1. Find stuck in-progress services
        stuck_result = await db.execute(
            select(CatalogService).where(
                CatalogService.status.in_(["Creating", "Building"]),
                CatalogService.created_at < cutoff,
            ).limit(20)
        )
        stuck = stuck_result.scalars().all()

        for svc in stuck:
            logger.warning(f"[deployment_worker] Marking stuck service as Failed: {svc.name} ({svc.id})")
            from sqlalchemy import update
            await db.execute(
                update(CatalogService)
                .where(CatalogService.id == svc.id)
                .values(status="Failed")
            )
            await ws_manager.send_to_tenant(svc.tenant_id, {
                "type": "service.failed",
                "data": {"service_id": svc.id, "service_name": svc.name, "reason": "Deployment timed out"},
            })

        await db.commit()

        # 2. Poll ArgoCD for Deploying services that have a gitops_app_name
        deploying_result = await db.execute(
            select(CatalogService).where(
                CatalogService.status == "Deploying",
                CatalogService.gitops_app_name.isnot(None),
            ).limit(20)
        )
        deploying = deploying_result.scalars().all()

        for svc in deploying:
            try:
                argocd_result = await db.execute(
                    select(Integration).where(
                        Integration.tenant_id == svc.tenant_id,
                        Integration.type == "argocd",
                        Integration.status == "connected",
                    ).limit(1)
                )
                argocd_int = argocd_result.scalar_one_or_none()
                client     = get_argocd_client(argocd_int.to_dict() if argocd_int else {})

                if not client:
                    continue

                health = await client.get_health_status(svc.gitops_app_name)
                sync   = await client.get_sync_status(svc.gitops_app_name)

                new_status = _health_to_status(health)
                if new_status != svc.status:
                    from sqlalchemy import update
                    await db.execute(
                        update(CatalogService)
                        .where(CatalogService.id == svc.id)
                        .values(status=new_status)
                    )
                    await db.commit()
                    await ws_manager.send_to_tenant(svc.tenant_id, {
                        "type": "service.synced",
                        "data": {
                            "service_id":  svc.id,
                            "service_name": svc.name,
                            "health":      health,
                            "sync_status": sync,
                            "status":      new_status,
                        },
                    })
                    logger.info(f"[deployment_worker] {svc.name}: {svc.status} → {new_status}")
            except Exception as exc:
                logger.debug(f"[deployment_worker] poll error for {svc.name}: {exc}")

        await db.commit()


def _health_to_status(health: str) -> str:
    return {
        "Healthy":     "Running",
        "Degraded":    "Failed",
        "Progressing": "Deploying",
        "Suspended":   "Stopped",
    }.get(health, "Deploying")
