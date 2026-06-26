from __future__ import annotations
"""
APScheduler-based background scheduler.
Replaces Celery Beat in dev mode (no Redis needed).
In production, Celery Beat handles scheduling instead.
"""
import asyncio
from app.utils.logger import logger


class BackgroundScheduler:
    """Runs periodic tasks as asyncio tasks inside FastAPI."""

    def __init__(self):
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("Background scheduler starting...")

        # K8s watchers disabled — causes event loop conflicts with asyncpg
        # TODO: rewrite watcher to use async K8s client
        logger.info("K8s watchers disabled (event loop safety)")

        # Schedule periodic tasks
        self._tasks = [
            asyncio.create_task(self._repeat(120,   self._sync_pods),      name="sync-pods"),
            asyncio.create_task(self._repeat(300,   self._sync_pipelines), name="sync-pipelines"),
            asyncio.create_task(self._repeat(3600,  self._sync_costs),     name="sync-costs"),
            asyncio.create_task(self._repeat(3600,  self._sync_security),  name="sync-security"),
            asyncio.create_task(self._repeat(21600, self._sync_assets),    name="sync-assets"),
            asyncio.create_task(self._repeat(86400, self._cleanup),        name="cleanup"),
            asyncio.create_task(self._repeat(21600, self._sync_ml),        name="sync-ml"),
            asyncio.create_task(self._repeat(1800,  self._run_recovery_scan), name="recovery-scan"),
        ]
        logger.info(f"Scheduler started {len(self._tasks)} periodic tasks")

    async def stop(self):
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        try:
            from app.integrations.kubernetes.watcher import stop_all_watchers
            await stop_all_watchers()
        except Exception:
            pass

        logger.info("Scheduler stopped")

    @staticmethod
    async def _repeat(interval_seconds: int, coro_func):
        """Run coro_func every interval_seconds forever."""
        # Wait before first run so startup isn't overloaded
        await asyncio.sleep(min(interval_seconds, 30))
        while True:
            try:
                await coro_func()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Scheduled task {coro_func.__name__} failed: {e}")
            await asyncio.sleep(interval_seconds)

    # ── Task implementations ──────────────────────────────────────────────────

    @staticmethod
    async def _sync_pods():
        try:
            from app.tasks.sync_pods import _sync_pods
            result = await _sync_pods()
            logger.info(f"Scheduled pod sync: {result}")
            # Broadcast real-time update to all connected tenants
            try:
                from app.api.v1.websocket.manager import ws_manager
                if ws_manager.total_connections > 0:
                    await ws_manager.broadcast({
                        "event": "pod.update",
                        "data": {"trigger": "sync", "synced": result if isinstance(result, int) else 0},
                    })
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Pod sync skipped: {e}")

    @staticmethod
    async def _sync_pipelines():
        try:
            from app.tasks.sync_pipelines import _sync_pipelines
            await _sync_pipelines()
            # Broadcast real-time update to all connected tenants
            try:
                from app.api.v1.websocket.manager import ws_manager
                if ws_manager.total_connections > 0:
                    await ws_manager.broadcast({
                        "event": "pipeline.update",
                        "data": {"trigger": "sync"},
                    })
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Pipeline sync skipped: {e}")

    @staticmethod
    async def _sync_costs():
        try:
            from app.tasks.sync_costs import sync_aws_costs_async
            result = await sync_aws_costs_async()
            logger.info(f"Scheduled cost sync: {result}")
        except Exception as e:
            logger.warning(f"Cost sync skipped: {e}")

    @staticmethod
    async def _sync_security():
        try:
            from app.tasks.sync_security import sync_aws_security_async
            result = await sync_aws_security_async()
            logger.info(f"Scheduled security sync: {result}")
        except Exception as e:
            logger.warning(f"Security sync skipped: {e}")

    @staticmethod
    async def _cleanup():
        try:
            from app.tasks.cleanup_old_data import cleanup_async
            await cleanup_async()
        except Exception as e:
            logger.warning(f"Cleanup skipped: {e}")

    @staticmethod
    async def _sync_assets():
        """
        Periodic full-asset sync — runs every 6 hours.
        Discovers and upserts assets from all connected integrations
        (GitHub, GitLab, AWS, Kubernetes, Docker) for every active tenant.
        """
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.tenant import Tenant
            from app.services.asset_discovery_service import AssetDiscoveryService
            from sqlalchemy import select

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Tenant).where(Tenant.is_active == True)
                )
                tenants = result.scalars().all()

            total: dict[str, int] = {}
            errors: list[str] = []
            for tenant in tenants:
                try:
                    async with AsyncSessionLocal() as session:
                        svc = AssetDiscoveryService(session)
                        sync_result = await svc.sync_all(tenant.id)
                        await session.commit()
                    for k, v in (sync_result.get("synced") or {}).items():
                        total[k] = total.get(k, 0) + v
                    errors.extend(sync_result.get("errors") or [])
                except Exception as exc:
                    errors.append(f"tenant={tenant.id[:8]}: {str(exc)[:100]}")
                    logger.warning(f"[scheduler:sync_assets] tenant={tenant.id[:8]} error={exc}")

            logger.info(f"[scheduler:sync_assets] done totals={total} errors={len(errors)}")

            # Broadcast update to connected websocket clients
            try:
                from app.api.v1.websocket.manager import ws_manager
                if ws_manager.total_connections > 0:
                    await ws_manager.broadcast({
                        "event": "assets.synced",
                        "data": {"totals": total, "error_count": len(errors)},
                    })
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"[scheduler:sync_assets] skipped: {e}")

    @staticmethod
    async def _sync_ml():
        try:
            from app.tasks.sync_ml_insights import sync_ml_insights_async
            result = await sync_ml_insights_async()
            logger.info(f"Scheduled ML sync: {result}")
        except Exception as e:
            logger.warning(f"ML sync skipped: {e}")

    @staticmethod
    async def _run_recovery_scan():
        """
        Trigger a recovery scan for stuck remediation executions.
        """
        try:
            from app.tasks.recovery_scan import _run_recovery_scan_async
            result = await _run_recovery_scan_async()
            logger.info(f"Scheduled recovery scan: {result}")
        except Exception as e:
            logger.warning(f"Recovery scan skipped: {e}")


# Global singleton
_scheduler = BackgroundScheduler()


async def start_scheduler():
    await _scheduler.start()


async def stop_scheduler():
    await _scheduler.stop()
