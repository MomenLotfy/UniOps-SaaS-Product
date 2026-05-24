from __future__ import annotations
"""
Kubernetes pod sync — two modes:
1. Full snapshot sync (Celery task or manual call) — fetches all pods at once
2. Real-time watcher (in watcher.py) — streams events continuously
"""
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from app.utils.logger import logger


# ── Celery task ───────────────────────────────────────────────────────────────
try:
    from app.core.celery_app import celery_app

    @celery_app.task(
        name="app.tasks.sync_pods.sync_all_pods",
        bind=True, max_retries=3, default_retry_delay=30, soft_time_limit=300,
    )
    def sync_all_pods(self):
        try:
            asyncio.run(_sync_pods())
            logger.info("Pod sync completed")
        except Exception as exc:
            logger.error(f"Pod sync failed: {exc}")
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
except Exception:
    pass


# ── Core async function ───────────────────────────────────────────────────────
async def _sync_pods(tenant_id: str | None = None) -> dict:
    """
    Full snapshot sync: list all pods from all K8s integrations and upsert into DB.
    Also enriches with metrics-server data if available.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.integration import Integration
    from app.models.pod import Pod
    from app.utils.encryption import decrypt

    summary = {"integrations": 0, "pods_synced": 0, "pods_deleted": 0}

    async with AsyncSessionLocal() as db:
        query = select(Integration).where(
            Integration.is_active == True,
            Integration.status == "connected",
            Integration.type == "kubernetes",
        )
        if tenant_id:
            query = query.where(Integration.tenant_id == tenant_id)

        result = await db.execute(query)
        integrations = result.scalars().all()
        logger.info(f"Snapshot sync: {len(integrations)} K8s integrations")

        for integration in integrations:
            try:
                # Decrypt credentials
                creds = {}
                for k, v in (integration.credentials or {}).items():
                    try:
                        creds[k] = decrypt(v)
                    except Exception:
                        creds[k] = v

                config = {**creds, **(integration.config or {})}

                from app.integrations.kubernetes.client import KubernetesClient
                client = KubernetesClient(config)

                # Fetch all pods across all namespaces
                pods_data = await client.list_all_pods()

                # Try to enrich with metrics-server data
                metrics = await client.get_pod_metrics()

                # Track which pods we saw this sync
                seen_names = set()

                for pod_data in pods_data:
                    pod_name = pod_data["name"]
                    pod_ns   = pod_data["namespace"]
                    seen_names.add((pod_name, pod_ns))

                    # Enrich with real usage if metrics available
                    if pod_name in metrics:
                        pod_data["cpu_usage"]    = metrics[pod_name].get("cpu_usage")
                        pod_data["memory_usage"] = metrics[pod_name].get("memory_usage")

                    # Upsert
                    existing = await db.execute(
                        select(Pod).where(
                            Pod.tenant_id == integration.tenant_id,
                            Pod.name == pod_name,
                            Pod.namespace == pod_ns,
                        )
                    )
                    pod = existing.scalar_one_or_none()

                    if pod:
                        _update_pod(pod, pod_data, integration)
                    else:
                        pod = _create_pod(pod_data, integration)
                        db.add(pod)

                    summary["pods_synced"] += 1

                # Remove pods that no longer exist in the cluster
                existing_pods = await db.execute(
                    select(Pod).where(
                        Pod.tenant_id == integration.tenant_id,
                        Pod.integration_id == integration.id,
                    )
                )
                for pod in existing_pods.scalars().all():
                    if (pod.name, pod.namespace) not in seen_names:
                        await db.delete(pod)
                        summary["pods_deleted"] += 1

                integration.last_sync = datetime.now(timezone.utc)
                await db.commit()
                summary["integrations"] += 1
                logger.info(f"Synced {len(pods_data)} pods for {integration.name}")

            except Exception as e:
                logger.error(f"Pod sync failed for {integration.id}: {e}")
                await db.rollback()

    return summary


def _update_pod(pod, data: dict, integration) -> None:
    fields = [
        "status", "phase", "node", "restart_count",
        "cpu_request", "cpu_limit", "cpu_usage",
        "memory_request", "memory_limit", "memory_usage",
        "containers", "labels",
    ]
    for f in fields:
        if data.get(f) is not None:
            setattr(pod, f, data[f])
    pod.cluster     = data.get("cluster") or integration.name
    pod.updated_at  = datetime.now(timezone.utc)


def _create_pod(data: dict, integration) -> object:
    from app.models.pod import Pod
    return Pod(
        tenant_id      = integration.tenant_id,
        integration_id = integration.id,
        name           = data["name"],
        namespace      = data.get("namespace", "default"),
        cluster        = data.get("cluster") or integration.name,
        node           = data.get("node"),
        status         = data.get("status", "Unknown"),
        phase          = data.get("phase"),
        restart_count  = data.get("restart_count", 0),
        cpu_request    = data.get("cpu_request"),
        cpu_limit      = data.get("cpu_limit"),
        cpu_usage      = data.get("cpu_usage"),
        memory_request = data.get("memory_request"),
        memory_limit   = data.get("memory_limit"),
        memory_usage   = data.get("memory_usage"),
        containers     = data.get("containers", []),
        labels         = data.get("labels", {}),
    )
