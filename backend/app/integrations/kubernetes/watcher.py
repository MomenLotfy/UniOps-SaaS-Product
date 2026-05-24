from __future__ import annotations
"""
Kubernetes pod watcher — streams real-time pod events via the K8s watch API.
Runs as a persistent async background task inside FastAPI (no Celery needed).
"""
import asyncio
from datetime import datetime, timezone
from app.integrations.kubernetes.client import KubernetesClient
from app.utils.logger import logger

# Global registry: integration_id → asyncio.Task
_watcher_tasks: dict[str, asyncio.Task] = {}


class KubernetesWatcher(KubernetesClient):

    async def watch_pods(self, tenant_id: str, integration_id: str, cluster_name: str) -> None:
        """
        Stream pod events from ALL namespaces.
        Automatically reconnects on disconnect. Runs forever until cancelled.
        """
        from kubernetes import watch as k8s_watch

        logger.info(f"K8s watcher starting: {cluster_name} (tenant={tenant_id})")

        while True:
            try:
                k8s = self._get_client()
                if not k8s:
                    logger.warning(f"K8s client unavailable for {cluster_name}, retrying in 30s")
                    await asyncio.sleep(30)
                    continue

                v1 = k8s.CoreV1Api()
                w = k8s_watch.Watch()

                # Run blocking watch in a thread so we don't block the event loop
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self._watch_blocking(w, v1, tenant_id, integration_id, cluster_name)
                )

            except asyncio.CancelledError:
                logger.info(f"K8s watcher cancelled: {cluster_name}")
                return
            except Exception as e:
                logger.error(f"K8s watcher error ({cluster_name}): {e} — reconnecting in 15s")
                await asyncio.sleep(15)

    def _watch_blocking(self, w, v1, tenant_id: str, integration_id: str, cluster_name: str):
        """Blocking watch loop — runs in thread pool."""
        import asyncio, threading

        loop = asyncio.new_event_loop()

        try:
            # Watch all namespaces, timeout=60s then re-connect (keeps connection fresh)
            for event in w.stream(
                v1.list_pod_for_all_namespaces,
                timeout_seconds=60,
                _request_timeout=65,
            ):
                event_type = event["type"]          # ADDED, MODIFIED, DELETED
                pod_obj = event["object"]

                pod_data = _extract_pod_data(pod_obj, cluster_name)

                # Save to DB (sync-safe wrapper)
                loop.run_until_complete(
                    _save_pod_event(tenant_id, integration_id, event_type, pod_data)
                )

        except Exception as e:
            logger.warning(f"K8s watch stream ended ({cluster_name}): {e}")
        finally:
            loop.close()


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
                # Update existing pod
                for field, value in pod_data.items():
                    if hasattr(pod, field) and value is not None:
                        setattr(pod, field, value)
                pod.updated_at = datetime.now(timezone.utc)
            else:
                # Insert new pod
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
