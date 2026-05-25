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

        # Start K8s watchers immediately
        try:
            from app.integrations.kubernetes.watcher import start_all_watchers
            await start_all_watchers()
        except Exception as e:
            logger.warning(f"Could not start K8s watchers: {e}")

        # Schedule periodic tasks
        self._tasks = [
            asyncio.create_task(self._repeat(120,  self._sync_pods),      name="sync-pods"),
            asyncio.create_task(self._repeat(300,  self._sync_pipelines),  name="sync-pipelines"),
            asyncio.create_task(self._repeat(3600, self._sync_costs),      name="sync-costs"),
            asyncio.create_task(self._repeat(3600, self._sync_security),   name="sync-security"),
            asyncio.create_task(self._repeat(86400, self._cleanup),        name="cleanup"),
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


# Global singleton
_scheduler = BackgroundScheduler()


async def start_scheduler():
    await _scheduler.start()


async def stop_scheduler():
    await _scheduler.stop()
