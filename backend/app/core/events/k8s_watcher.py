from __future__ import annotations
"""
Kubernetes Watcher — polls clusters for pod/event changes and emits
events into the in-process event bus.

Runs as a background asyncio task started from main.py lifespan.

Design:
  - One watcher loop per connected cluster in the DB
  - 30-second poll cycle (fast enough for real-time feel, light on API)
  - Tracks last-seen state to emit deltas only (created / updated / failed)
  - All events are tenant + cluster scoped
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Poll interval for each cluster watcher (seconds)
_POLL_INTERVAL = 30
# Debounce: minimum seconds between identical pod events
_DEBOUNCE = 60


class ClusterWatcher:
    """
    Watches a single Kubernetes cluster for pod state changes.
    Emits pod.created / pod.updated / pod.failed / pod.restarted events.
    """

    def __init__(
        self,
        cluster_id: str,
        tenant_id: str,
        k8s_client,
    ):
        self.cluster_id = cluster_id
        self.tenant_id  = tenant_id
        self._client    = k8s_client
        self._pod_state: dict[str, dict] = {}   # pod_name → last known state
        self._running   = False

    async def start(self) -> None:
        self._running = True
        logger.info(f"[k8s_watcher] Starting watcher for cluster {self.cluster_id}")
        while self._running:
            try:
                await self._poll()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning(
                    f"[k8s_watcher] cluster {self.cluster_id} poll error: {exc}"
                )
            await asyncio.sleep(_POLL_INTERVAL)

    def stop(self) -> None:
        self._running = False

    async def _poll(self) -> None:
        from app.core.events.event_bus import event_bus

        try:
            pods = await asyncio.wait_for(
                self._client.list_all_pods(), timeout=20.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"[k8s_watcher] cluster {self.cluster_id} list_all_pods timeout")
            return

        current_names = set()
        for pod in pods:
            name      = pod.get("name", "")
            namespace = pod.get("namespace", "default")
            status    = pod.get("status", "Unknown")
            restarts  = pod.get("restart_count", 0)
            key       = f"{namespace}/{name}"
            current_names.add(key)

            prev = self._pod_state.get(key)

            if prev is None:
                # New pod
                self._pod_state[key] = {"status": status, "restarts": restarts}
                await event_bus.emit(
                    "pod.created",
                    {
                        "pod":        name,
                        "namespace":  namespace,
                        "status":     status,
                        "restarts":   restarts,
                        "cluster_id": self.cluster_id,
                    },
                    tenant_id=self.tenant_id,
                    cluster_id=self.cluster_id,
                )
                continue

            changed = False

            if status != prev["status"]:
                changed = True
                evt = "pod.updated"
                if status in ("Failed", "Error", "CrashLoopBackOff", "OOMKilled"):
                    evt = "pod.failed"
                await event_bus.emit(
                    evt,
                    {
                        "pod":        name,
                        "namespace":  namespace,
                        "status":     status,
                        "prev_status":prev["status"],
                        "cluster_id": self.cluster_id,
                    },
                    tenant_id=self.tenant_id,
                    cluster_id=self.cluster_id,
                )

            if restarts > prev["restarts"]:
                changed = True
                await event_bus.emit(
                    "pod.restarted",
                    {
                        "pod":        name,
                        "namespace":  namespace,
                        "restarts":   restarts,
                        "prev_restarts": prev["restarts"],
                        "cluster_id": self.cluster_id,
                    },
                    tenant_id=self.tenant_id,
                    cluster_id=self.cluster_id,
                )

            if changed:
                self._pod_state[key] = {"status": status, "restarts": restarts}

        # Pods that disappeared
        for key in list(self._pod_state.keys()):
            if key not in current_names:
                namespace, name = key.split("/", 1)
                del self._pod_state[key]
                await event_bus.emit(
                    "pod.deleted",
                    {
                        "pod":        name,
                        "namespace":  namespace,
                        "cluster_id": self.cluster_id,
                    },
                    tenant_id=self.tenant_id,
                    cluster_id=self.cluster_id,
                )


# ── Global watcher registry ───────────────────────────────────────────────────

_watchers: dict[str, tuple[ClusterWatcher, asyncio.Task]] = {}


async def start_cluster_watcher(
    cluster_id: str,
    tenant_id: str,
    k8s_client,
) -> None:
    """Start a background watcher for one cluster (idempotent)."""
    if cluster_id in _watchers:
        return
    watcher = ClusterWatcher(cluster_id, tenant_id, k8s_client)
    task    = asyncio.create_task(
        watcher.start(), name=f"k8s-watcher-{cluster_id[:8]}"
    )
    _watchers[cluster_id] = (watcher, task)
    logger.info(f"[k8s_watcher] registered watcher for cluster {cluster_id}")


async def stop_cluster_watcher(cluster_id: str) -> None:
    """Stop and remove the watcher for a cluster."""
    entry = _watchers.pop(cluster_id, None)
    if entry:
        watcher, task = entry
        watcher.stop()
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=5)
        except Exception:
            pass


async def stop_all_watchers() -> None:
    for cluster_id in list(_watchers.keys()):
        await stop_cluster_watcher(cluster_id)


async def bootstrap_watchers() -> None:
    """
    Called at startup — scans the DB for connected clusters and starts a
    watcher for each one that has a kubeconfig or reachable API server.

    Non-fatal: if no clusters are connected, simply logs and returns.
    """
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.cluster import Cluster
        from app.core.kubernetes.client_factory import KubernetesClientFactory
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Cluster).where(Cluster.status == "connected")
            )
            clusters = result.scalars().all()

        if not clusters:
            logger.info("[k8s_watcher] No connected clusters — watchers not started")
            return

        factory = KubernetesClientFactory()
        for cluster in clusters:
            try:
                client = await factory.get_client(cluster.id, cluster.tenant_id)
                if client:
                    await start_cluster_watcher(
                        str(cluster.id),
                        str(cluster.tenant_id),
                        client,
                    )
            except Exception as exc:
                logger.warning(
                    f"[k8s_watcher] Could not start watcher for "
                    f"cluster {cluster.id}: {exc}"
                )

        logger.info(f"[k8s_watcher] Bootstrap complete — {len(_watchers)} watcher(s) active")

    except Exception as exc:
        logger.warning(f"[k8s_watcher] bootstrap_watchers skipped: {exc}")
