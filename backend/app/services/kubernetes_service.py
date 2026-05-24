from __future__ import annotations
"""Kubernetes service — pod management, cluster health, and real cluster actions."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pod import Pod
from app.models.integration import Integration
from app.models.audit_log import AuditLog
from app.schemas.pod import PodResponse, PodStats, PodActionResult
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundError, ForbiddenError, IntegrationError
from app.services.base import BaseService
from app.utils.logger import logger


def _decrypt_integration_creds(integration: Integration) -> dict:
    """Decrypt stored credentials, skip non-encrypted fields gracefully."""
    from app.utils.encryption import decrypt
    creds = {}
    for k, v in (integration.credentials or {}).items():
        try:
            creds[k] = decrypt(v)
        except Exception:
            creds[k] = v
    return creds


class KubernetesService(BaseService):

    # ── Read operations ───────────────────────────────────────────────────────

    async def list_pods(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        namespace: Optional[str] = None,
        cluster: Optional[str] = None,
        status: Optional[str] = None,
    ) -> PaginatedResponse:
        query = select(Pod).where(Pod.tenant_id == tenant_id)
        if namespace:
            query = query.where(Pod.namespace == namespace)
        if cluster:
            query = query.where(Pod.cluster == cluster)
        if status:
            query = query.where(Pod.status == status)

        total = await self._count(query)
        query = query.order_by(Pod.restart_count.desc(), Pod.created_at.desc())
        items = await self._paginate(query, page, page_size)

        return PaginatedResponse(
            data=[PodResponse.model_validate(p) for p in items],
            total=total, page=page, page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def get_pod(self, pod_id: str) -> PodResponse:
        pod = await self._get_by_id(Pod, pod_id)
        return PodResponse.model_validate(pod)

    async def get_stats(self, tenant_id: str) -> PodStats:
        result = await self.db.execute(
            select(Pod.status, Pod.cpu_usage, Pod.memory_usage,
                   Pod.cpu_limit, Pod.memory_limit, Pod.restart_count)
            .where(Pod.tenant_id == tenant_id)
        )
        rows = result.fetchall()
        stats = PodStats(total=len(rows))
        cpu_usages, mem_usages = [], []

        for status, cpu_u, mem_u, cpu_l, mem_l, restarts in rows:
            if status == "Running":   stats.running += 1
            elif status == "Pending": stats.pending += 1
            elif status in ("Failed", "Error", "CrashLoopBackOff"):
                stats.failed += 1
            if restarts and restarts > 5:
                stats.high_restart_count += 1
            if cpu_u is not None and cpu_l and cpu_l > 0:
                cpu_usages.append((cpu_u / cpu_l) * 100)
            if mem_u is not None and mem_l and mem_l > 0:
                mem_usages.append((mem_u / mem_l) * 100)

        if cpu_usages:
            stats.cpu_usage_pct = round(sum(cpu_usages) / len(cpu_usages), 1)
        if mem_usages:
            stats.memory_usage_pct = round(sum(mem_usages) / len(mem_usages), 1)

        return stats

    async def get_namespaces(self, tenant_id: str) -> list[str]:
        result = await self.db.execute(
            select(Pod.namespace).where(Pod.tenant_id == tenant_id).distinct()
        )
        return [row[0] for row in result.fetchall() if row[0]]

    async def get_clusters(self, tenant_id: str) -> list[str]:
        result = await self.db.execute(
            select(Pod.cluster).where(Pod.tenant_id == tenant_id).distinct()
        )
        return [row[0] for row in result.fetchall() if row[0]]

    async def get_pod_events(self, pod_id: str) -> list[dict]:
        """Fetch live K8s events for a pod (useful for debugging CrashLoops)."""
        pod = await self._get_by_id(Pod, pod_id)
        client = await self._get_k8s_client(pod)
        return await client.get_pod_events(pod.name, pod.namespace)

    async def get_pod_logs(
        self, pod_id: str, tail: int = 200, container: str | None = None
    ) -> str:
        """Fetch last N log lines from a pod via Kubernetes API."""
        pod = await self._get_by_id(Pod, pod_id)
        client = await self._get_k8s_client(pod)
        try:
            k8s = client._get_client()
            if not k8s:
                return "Kubernetes client unavailable"
            v1 = k8s.CoreV1Api()
            kwargs: dict = {
                "name":       pod.name,
                "namespace":  pod.namespace,
                "tail_lines": tail,
                "_request_timeout": 15,
            }
            if container:
                kwargs["container"] = container
            logs: str = v1.read_namespaced_pod_log(**kwargs)
            return logs or "(no output)"
        except Exception as e:
            logger.warning(f"get_pod_logs failed ({pod.namespace}/{pod.name}): {e}")
            return f"Could not fetch logs: {e}"

    # ── Write / Action operations ─────────────────────────────────────────────

    async def delete_pod(self, pod_id: str, deleted_by: str) -> PodActionResult:
        """
        Delete pod from Kubernetes cluster immediately (grace_period=0).
        After success, removes the pod record from our DB too.
        K8s controllers (Deployments etc.) will recreate the pod automatically.
        """
        pod, client = await self._resolve_pod_and_client(pod_id)

        # Execute on cluster
        result = await client.delete_pod(pod.name, pod.namespace)
        if not result["success"]:
            raise IntegrationError("Kubernetes", result.get("error", "Delete failed"))

        # Remove stale DB record — watcher will re-insert when K8s recreates it
        pod_name = pod.name
        pod_namespace = pod.namespace
        await self.db.delete(pod)

        # Audit log
        await self._write_audit(
            tenant_id=pod.tenant_id,
            user_id=deleted_by,
            action="pod.delete",
            resource="pod",
            resource_id=pod_id,
            details={"name": pod_name, "namespace": pod_namespace},
        )

        logger.info(f"[audit] pod.delete {pod_namespace}/{pod_name} by {deleted_by}")
        return PodActionResult(
            success=True,
            action="delete",
            pod_name=pod_name,
            namespace=pod_namespace,
            message=f"Pod '{pod_name}' deleted from cluster",
        )

    async def restart_pod(self, pod_id: str, restarted_by: str) -> PodActionResult:
        """
        Graceful restart: deletes pod with grace_period=30s.
        The owning controller (Deployment/StatefulSet/DaemonSet) schedules
        a replacement immediately. For standalone pods, behaviour is the same
        as delete.
        """
        pod, client = await self._resolve_pod_and_client(pod_id)

        result = await client.restart_pod(pod.name, pod.namespace)
        if not result["success"]:
            raise IntegrationError("Kubernetes", result.get("error", "Restart failed"))

        # Mark pod as restarting in our DB — watcher will update when new pod appears
        pod.status = "Terminating"
        pod.updated_at = datetime.now(timezone.utc)

        await self._write_audit(
            tenant_id=pod.tenant_id,
            user_id=restarted_by,
            action="pod.restart",
            resource="pod",
            resource_id=pod_id,
            details={
                "name": pod.name,
                "namespace": pod.namespace,
                "has_controller": result.get("has_controller", False),
            },
        )

        logger.info(f"[audit] pod.restart {pod.namespace}/{pod.name} by {restarted_by}")
        return PodActionResult(
            success=True,
            action="restart",
            pod_name=pod.name,
            namespace=pod.namespace,
            message=result.get("message", f"Pod '{pod.name}' restart initiated"),
            has_controller=result.get("has_controller"),
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _resolve_pod_and_client(self, pod_id: str):
        """Load pod + its integration + build a live K8s client. Raises on any failure."""
        pod = await self._get_by_id(Pod, pod_id)
        client = await self._get_k8s_client(pod)
        return pod, client

    async def _get_k8s_client(self, pod_or_tenant):
        """
        Build KubernetesClient.
        Accepts either a Pod object (old callers) or a tenant_id string (new cluster-level endpoints).
        """
        from app.integrations.kubernetes.client import KubernetesClient

        if isinstance(pod_or_tenant, str):
            # Called with tenant_id directly — find the first active K8s integration
            result = await self.db.execute(
                select(Integration).where(
                    Integration.tenant_id == pod_or_tenant,
                    Integration.type == "kubernetes",
                    Integration.is_active == True,
                    Integration.status == "connected",
                ).limit(1)
            )
            integration = result.scalar_one_or_none()
            if not integration:
                return None
        else:
            # Called with a Pod object
            pod = pod_or_tenant
            if not pod.integration_id:
                raise IntegrationError("Kubernetes", "Pod has no integration associated")
            integration = await self._get_or_none(Integration, pod.integration_id)
            if not integration:
                raise IntegrationError("Kubernetes", "Integration record not found")
            if not integration.is_active or integration.status != "connected":
                raise IntegrationError(
                    "Kubernetes",
                    f"Integration '{integration.name}' is not connected (status={integration.status})",
                )

        creds  = _decrypt_integration_creds(integration)
        config = {**creds, **(integration.config or {})}
        return KubernetesClient(config)

    async def _write_audit(
        self,
        tenant_id: str,
        user_id: str,
        action: str,
        resource: str,
        resource_id: str,
        details: dict,
        status: str = "success",
    ) -> None:
        try:
            log = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource=resource,
                resource_id=resource_id,
                details=details,
                status=status,
            )
            self.db.add(log)
            await self.db.flush()
        except Exception as e:
            # Audit failures must never block the main action
            logger.warning(f"Audit log write failed (non-fatal): {e}")


    async def exec_pod(
        self,
        pod_id: str,
        command: str,
        container: str | None = None,
    ) -> str:
        """Execute a shell command in a pod and return combined stdout/stderr."""
        from sqlalchemy import select
        from app.models.pod import Pod

        result = await self.db.execute(select(Pod).where(Pod.id == pod_id))
        pod    = result.scalar_one_or_none()
        if not pod:
            return f"Pod {pod_id} not found"

        client = await self._get_k8s_client(pod.tenant_id)
        if not client:
            return "Kubernetes client unavailable"

        output = await client.exec_pod(
            name=pod.name,
            namespace=pod.namespace,
            command=command,
            container=container,
        )
        return output

    async def scale_deployment(
        self,
        deployment_name: str,
        namespace: str,
        replicas: int,
        triggered_by: str,
    ) -> dict:
        """Scale a Kubernetes Deployment to the specified replica count."""
        from sqlalchemy import select
        from app.models.integration import Integration

        # Get first kubernetes integration for this request (tenant resolved by dep)
        result = await self.db.execute(
            select(Integration).where(
                Integration.type == "kubernetes",
                Integration.is_active == True,
                Integration.status == "connected",
            ).limit(1)
        )
        integration = result.scalar_one_or_none()
        if not integration:
            return {"success": False, "error": "No Kubernetes integration connected"}

        client = await self._get_k8s_client(integration.tenant_id)
        if not client:
            return {"success": False, "error": "Kubernetes client unavailable"}

        result = await client.scale_deployment(
            name=deployment_name,
            namespace=namespace,
            replicas=replicas,
        )
        if result.get("success"):
            await self._write_audit(
                tenant_id=integration.tenant_id,
                user_id=triggered_by,
                action="scale_deployment",
                resource="deployment",
                resource_id=f"{namespace}/{deployment_name}",
                details={"replicas": replicas, "namespace": namespace},
            )
        return result
