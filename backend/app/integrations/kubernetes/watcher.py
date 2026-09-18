from __future__ import annotations
"""
Kubernetes pod watcher — streams real-time pod events via the K8s Watch API.

Design:
  - One asyncio task per connected K8s integration.
  - The (blocking) kubernetes Watch stream runs in a thread; events are
    handed to the main event loop with `loop.call_soon_threadsafe` so DB
    writes (asyncpg/aiosqlite) and WebSocket emits always happen on the
    correct loop — never inside the executor thread (the old code created a
    second event loop in the thread and crashed against asyncpg).
  - On stream end (server closes the connection) we reconnect with backoff.

Registration is idempotent per integration and supports stop/start.
"""
import asyncio
from datetime import datetime, timezone
from app.integrations.kubernetes.client import KubernetesClient
from app.utils.logger import logger

# Global registry: integration_id → asyncio.Task
_watcher_tasks: dict[str, asyncio.Task] = {}


class KubernetesWatcher(KubernetesClient):

    async def watch_pods(self, tenant_id: str, integration_id: str, cluster_name: str) -> None:
        """Stream pod events from ALL namespaces. Reconnects on failure; task-cancel stops."""
        from kubernetes import watch as k8s_watch

        logger.info(f"K8s watcher starting: {cluster_name} (tenant={tenant_id})")
        backoff = 5

        loop = asyncio.get_running_loop()

        while True:
            try:
                k8s = self._get_client()
                if not k8s:
                    logger.warning(f"K8s client unavailable for {cluster_name}, retrying in 30s")
                    await asyncio.sleep(30)
                    continue

                v1 = k8s.CoreV1Api()
                w  = k8s_watch.Watch()

                def _blocking_watch():
                    """Runs on the executor thread — pushes events into the queue."""
                    try:
                        for event in w.stream(
                            v1.list_pod_for_all_namespaces,
                            timeout_seconds=60,
                            _request_timeout=65,
                        ):
                            evt  = event["type"]
                            data = _extract_pod_data(event["object"], cluster_name)
                            loop.call_soon_threadsafe(
                                _pending.put_nowait, (evt, data)
                            )
                    except Exception as e:
                        logger.warning(f"K8s watch stream ended ({cluster_name}): {e}")

                _pending: asyncio.Queue = asyncio.Queue(maxsize=2000)
                fut = loop.run_in_executor(None, _blocking_watch)

                try:
                    # Consume events on the main loop; periodically verify stream liveness
                    while True:
                        try:
                            evt, data = await asyncio.wait_for(_pending.get(), timeout=75)
                            await _save_pod_event(tenant_id, integration_id, evt, data)
                            await _emit_ws(tenant_id, cluster_name, evt, data)
                        except asyncio.TimeoutError:
                            if fut.done():
                                break          # stream ended → outer loop reconnects
                finally:
                    try:
                        w.stop()
                    except Exception:
                        pass
                    if not fut.done():
                        fut.cancel()

                backoff = 5  # reconnect fast after graceful stream end

            except asyncio.CancelledError:
                logger.info(f"K8s watcher cancelled: {cluster_name}")
                return
            except Exception as e:
                logger.error(f"K8s watcher error ({cluster_name}): {e} — reconnecting in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 120)


async def _emit_ws(tenant_id: str, cluster_name: str, event_type: str, pod_data: dict) -> None:
    """Forward watch events to the WebSocket + event bus (UI live refresh)."""
    try:
        from app.core.events.event_bus import event_bus
        name_map = {"ADDED": "pod.created", "MODIFIED": "pod.updated", "DELETED": "pod.deleted"}
        evt = name_map.get(event_type)
        if evt is None:
            return
        status = pod_data.get("status") or ""
        if status in ("Failed", "Error", "CrashLoopBackOff", "OOMKilled"):
            evt = "pod.failed"
        await event_bus.emit(
            evt,
            {
                "pod":       pod_data.get("name"),
                "name":      pod_data.get("name"),
                "namespace": pod_data.get("namespace"),
                "status":    status,
                "cluster":   cluster_name,
                "restart_count": pod_data.get("restart_count", 0),
            },
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.debug(f"[watcher] event emit failed: {exc}")


# ── Pod event persistence ─────────────────────────────────────────────────────

async def _save_pod_event(tenant_id: str, integration_id: str, event_type: str, pod_data: dict):
    """Upsert pod into database on each watch event."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.pod import Pod
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                select(Pod).where(
                    Pod.tenant_id == tenant_id,
                    Pod.name == pod_data["name"],
                    Pod.namespace == pod_data["namespace"],
                )
            )
            pod = existing.scalar_one_or_none()

            if event_type == "DELETED":
                if pod:
                    await db.delete(pod)
                    await db.commit()
                return

            if pod:
                for field, value in pod_data.items():
                    if hasattr(pod, field) and value is not None:
                        setattr(pod, field, value)
                pod.updated_at = datetime.now(timezone.utc)
            else:
                pod = Pod(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    **{k: v for k, v in pod_data.items() if hasattr(Pod, k)},
                )
                db.add(pod)

            await db.commit()

    except Exception as e:
        logger.error(f"Failed to save pod event: {e}")


def _extract_pod_data(pod_obj, cluster_name: str) -> dict:
    """Extract relevant fields from a K8s pod object."""
    from app.integrations.kubernetes.client import _parse_cpu, _parse_memory

    meta   = pod_obj.metadata
    spec   = pod_obj.spec
    status = pod_obj.status

    restart_count = sum(
        (cs.restart_count or 0) for cs in (status.container_statuses or [])
    )

    containers_info = [
        {
            "name": cs.name,
            "ready": cs.ready,
            "restarts": cs.restart_count,
            "state": (
                "running"     if cs.state.running     else
                "terminated"  if cs.state.terminated  else
                "waiting"
            ),
            "image": cs.image,
        }
        for cs in (status.container_statuses or [])
    ]

    cpu_req = cpu_lim = mem_req = mem_lim = None
    if spec and spec.containers:
        c = spec.containers[0]
        if c.resources:
            req = c.resources.requests or {}
            lim = c.resources.limits or {}
            cpu_req = _parse_cpu(req.get("cpu"))
            cpu_lim = _parse_cpu(lim.get("cpu"))
            mem_req = _parse_memory(req.get("memory"))
            mem_lim = _parse_memory(lim.get("memory"))

    return {
        "name":           meta.name,
        "namespace":      meta.namespace or "default",
        "cluster":        cluster_name,
        "node":           spec.node_name if spec else None,
        "status":         status.phase or "Unknown",
        "phase":          status.phase,
        "restart_count":  restart_count,
        "cpu_request":    cpu_req,
        "cpu_limit":      cpu_lim,
        "memory_request": mem_req,
        "memory_limit":   mem_lim,
        "containers":     containers_info,
        "labels":         dict(meta.labels or {}),
    }


# ── Watcher manager ───────────────────────────────────────────────────────────

async def start_watcher(tenant_id: str, integration_id: str, config: dict, name: str):
    """Start a persistent watcher task for one K8s integration."""
    if integration_id in _watcher_tasks:
        t = _watcher_tasks[integration_id]
        if not t.done():
            logger.info(f"Watcher already running for {name}")
            return

    watcher = KubernetesWatcher(config)
    task = asyncio.create_task(
        watcher.watch_pods(tenant_id, integration_id, name),
        name=f"k8s-watcher-{integration_id[:8]}",
    )
    _watcher_tasks[integration_id] = task
    logger.info(f"K8s watcher started: {name}")


async def stop_watcher(integration_id: str):
    """Cancel the watcher task for an integration."""
    task = _watcher_tasks.pop(integration_id, None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info(f"K8s watcher stopped: {integration_id}")


async def start_all_watchers():
    """Called on app startup — starts watchers for all connected K8s integrations."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.integration import Integration
        from app.utils.encryption import decrypt
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Integration).where(
                    Integration.type == "kubernetes",
                    Integration.is_active == True,
                    Integration.status == "connected",
                )
            )
            integrations = result.scalars().all()

        for intg in integrations:
            creds = {}
            for k, v in (intg.credentials or {}).items():
                try:
                    creds[k] = decrypt(v)
                except Exception:
                    creds[k] = v

            config = {**creds, **(intg.config or {})}
            await start_watcher(intg.tenant_id, intg.id, config, intg.name)

        logger.info(f"Started {len(integrations)} K8s watchers on startup")

    except Exception as e:
        logger.error(f"Failed to start K8s watchers: {e}")


async def stop_all_watchers():
    """Called on app shutdown."""
    ids = list(_watcher_tasks.keys())
    for integration_id in ids:
        await stop_watcher(integration_id)
    logger.info("All K8s watchers stopped")
