from __future__ import annotations
"""
ClusterService — Multi-Cluster Kubernetes Management.
Stores cluster configs in DB; uses kubernetes-client to introspect each cluster.
"""
import base64
import io
import logging
import tempfile
import os
from datetime import datetime, timezone
from typing import Optional

import yaml
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.cluster import Cluster
from app.schemas.cluster import (
    ClusterCreate, ClusterUpdate, ClusterResponse,
    ClusterNode, ClusterNamespace, ClusterService,
    ClusterIngress, ClusterDeployment, NodeCondition,
)
from app.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


def _encode_kubeconfig(raw: str) -> str:
    return base64.b64encode(raw.encode()).decode()


def _decode_kubeconfig(encoded: str) -> str:
    return base64.b64decode(encoded.encode()).decode()


def _age_from_ts(ts) -> Optional[str]:
    """Human-readable age string from a datetime or ISO string."""
    if not ts:
        return None
    try:
        if isinstance(ts, str):
            from dateutil.parser import parse
            ts = parse(ts)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        s = int(delta.total_seconds())
        if s < 60:     return f"{s}s"
        if s < 3600:   return f"{s // 60}m"
        if s < 86400:  return f"{s // 3600}h"
        return f"{s // 86400}d"
    except Exception:
        return None


def _get_k8s_client(kubeconfig_yaml: str):
    """Build a kubernetes ApiClient from a kubeconfig YAML string."""
    import kubernetes as k8s
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    try:
        tmp.write(kubeconfig_yaml)
        tmp.flush()
        tmp.close()
        cfg = k8s.config.load_kube_config(config_file=tmp.name)
        api_client = k8s.client.ApiClient()
        return api_client
    finally:
        os.unlink(tmp.name)


def _get_default_k8s_client():
    """Use in-cluster or default kubeconfig for the primary connected cluster."""
    import kubernetes as k8s
    try:
        k8s.config.load_incluster_config()
    except Exception:
        try:
            k8s.config.load_kube_config()
        except Exception:
            return None
    return k8s.client.ApiClient()


class ClusterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── CRUD ────────────────────────────────────────────────────────────────

    async def list_clusters(self, tenant_id: str) -> list[ClusterResponse]:
        result = await self.db.execute(
            select(Cluster)
            .where(Cluster.tenant_id == tenant_id)
            .order_by(Cluster.created_at.asc())
        )
        clusters = result.scalars().all()
        return [ClusterResponse.model_validate(c) for c in clusters]

    async def get_cluster(self, tenant_id: str, cluster_id: str) -> Cluster:
        result = await self.db.execute(
            select(Cluster).where(Cluster.id == cluster_id, Cluster.tenant_id == tenant_id)
        )
        cluster = result.scalar_one_or_none()
        if not cluster:
            raise NotFoundError(f"Cluster {cluster_id} not found")
        return cluster

    async def add_cluster(self, tenant_id: str, data: ClusterCreate) -> ClusterResponse:
        encoded_kc = _encode_kubeconfig(data.kubeconfig) if data.kubeconfig else None
        cluster = Cluster(
            tenant_id=tenant_id,
            name=data.name,
            provider=data.provider,
            region=data.region,
            environment=data.environment,
            api_server_url=data.api_server_url,
            kubeconfig_encrypted=encoded_kc,
            status="pending",
        )
        self.db.add(cluster)
        await self.db.commit()
        await self.db.refresh(cluster)
        logger.info(f"[cluster:add] tenant={tenant_id[:8]} name={data.name} provider={data.provider}")

        # Fire-and-forget health check
        if encoded_kc or data.api_server_url:
            try:
                await self._run_health_check(cluster)
                await self.db.commit()
                await self.db.refresh(cluster)
            except Exception as e:
                logger.warning(f"[cluster:add] initial health check failed: {e}")

        return ClusterResponse.model_validate(cluster)

    async def update_cluster(self, tenant_id: str, cluster_id: str, data: ClusterUpdate) -> ClusterResponse:
        cluster = await self.get_cluster(tenant_id, cluster_id)
        if data.name is not None:           cluster.name = data.name
        if data.region is not None:         cluster.region = data.region
        if data.environment is not None:    cluster.environment = data.environment
        if data.api_server_url is not None: cluster.api_server_url = data.api_server_url
        if data.kubeconfig is not None:     cluster.kubeconfig_encrypted = _encode_kubeconfig(data.kubeconfig)
        await self.db.commit()
        await self.db.refresh(cluster)
        return ClusterResponse.model_validate(cluster)

    async def delete_cluster(self, tenant_id: str, cluster_id: str) -> None:
        cluster = await self.get_cluster(tenant_id, cluster_id)
        await self.db.delete(cluster)
        await self.db.commit()
        logger.info(f"[cluster:delete] tenant={tenant_id[:8]} cluster_id={cluster_id}")

    # ── Health check / test connection ───────────────────────────────────────

    async def test_connection(self, tenant_id: str, cluster_id: str) -> dict:
        cluster = await self.get_cluster(tenant_id, cluster_id)
        try:
            await self._run_health_check(cluster)
            await self.db.commit()
            return {"status": cluster.status, "k8s_version": cluster.k8s_version,
                    "node_count": cluster.node_count, "message": "Connection successful"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _run_health_check(self, cluster: Cluster) -> None:
        import kubernetes as k8s

        client = self._build_client(cluster)
        if not client:
            cluster.status = "disconnected"
            cluster.error_message = "No kubeconfig provided and no in-cluster config available"
            cluster.last_health_check = datetime.now(timezone.utc)
            return

        try:
            v1 = k8s.client.CoreV1Api(client)
            version_api = k8s.client.VersionApi(client)

            # K8s version
            ver = version_api.get_code()
            cluster.k8s_version = f"{ver.major}.{ver.minor}"

            # Nodes
            nodes = v1.list_node()
            cluster.node_count = len(nodes.items)

            # Pod count
            pods = v1.list_pod_for_all_namespaces()
            cluster.pod_count = len(pods.items)

            # Simple CPU/memory estimate from pods requests
            cpu_total, mem_total, cpu_used, mem_used = 0.0, 0.0, 0.0, 0.0
            for node in nodes.items:
                alloc = node.status.allocatable or {}
                cpu_total  += _parse_cpu(alloc.get("cpu", "0"))
                mem_total  += _parse_memory(alloc.get("memory", "0"))
            for pod in pods.items:
                for c in (pod.spec.containers or []):
                    req = (c.resources.requests or {}) if c.resources else {}
                    cpu_used += _parse_cpu(req.get("cpu", "0"))
                    mem_used += _parse_memory(req.get("memory", "0"))

            cluster.cpu_usage_pct    = round(min(cpu_used / cpu_total * 100, 100), 1) if cpu_total else 0.0
            cluster.memory_usage_pct = round(min(mem_used / mem_total * 100, 100), 1) if mem_total else 0.0
            cluster.status           = "connected"
            cluster.error_message    = None
            cluster.last_health_check = datetime.now(timezone.utc)

        except Exception as e:
            cluster.status        = "error"
            cluster.error_message = str(e)[:500]
            cluster.last_health_check = datetime.now(timezone.utc)
            raise

    # ── Detail resources ─────────────────────────────────────────────────────

    async def get_nodes(self, tenant_id: str, cluster_id: str) -> list[ClusterNode]:
        cluster = await self.get_cluster(tenant_id, cluster_id)
        import kubernetes as k8s
        client = self._build_client(cluster)
        if not client:
            return []
        v1 = k8s.client.CoreV1Api(client)
        nodes_resp = v1.list_node()
        result = []
        for n in nodes_resp.items:
            roles = [
                lbl.replace("node-role.kubernetes.io/", "")
                for lbl in (n.metadata.labels or {})
                if lbl.startswith("node-role.kubernetes.io/")
            ] or ["worker"]
            ready = "Unknown"
            conds = []
            for c in (n.status.conditions or []):
                conds.append(NodeCondition(type=c.type, status=c.status))
                if c.type == "Ready":
                    ready = "Ready" if c.status == "True" else "NotReady"
            alloc = n.status.allocatable or {}
            cap   = n.status.capacity    or {}
            info  = n.status.node_info
            result.append(ClusterNode(
                name=n.metadata.name,
                status=ready,
                roles=roles,
                cpu_capacity=cap.get("cpu"),
                memory_capacity=cap.get("memory"),
                cpu_allocatable=alloc.get("cpu"),
                memory_allocatable=alloc.get("memory"),
                os_image=info.os_image if info else None,
                kubelet_version=info.kubelet_version if info else None,
                conditions=conds,
                age=_age_from_ts(n.metadata.creation_timestamp),
            ))
        return result

    async def get_namespaces(self, tenant_id: str, cluster_id: str) -> list[ClusterNamespace]:
        cluster = await self.get_cluster(tenant_id, cluster_id)
        import kubernetes as k8s
        client = self._build_client(cluster)
        if not client:
            return []
        v1 = k8s.client.CoreV1Api(client)
        resp = v1.list_namespace()
        return [
            ClusterNamespace(
                name=ns.metadata.name,
                status=ns.status.phase or "Active",
                age=_age_from_ts(ns.metadata.creation_timestamp),
                labels=dict(ns.metadata.labels or {}),
            )
            for ns in resp.items
        ]

    async def get_deployments(self, tenant_id: str, cluster_id: str, namespace: Optional[str] = None) -> list[ClusterDeployment]:
        cluster = await self.get_cluster(tenant_id, cluster_id)
        import kubernetes as k8s
        client = self._build_client(cluster)
        if not client:
            return []
        apps = k8s.client.AppsV1Api(client)
        if namespace:
            resp = apps.list_namespaced_deployment(namespace)
        else:
            resp = apps.list_deployment_for_all_namespaces()
        result = []
        for d in resp.items:
            spec = d.spec
            status = d.status
            ready = status.ready_replicas or 0
            desired = spec.replicas or 0
            avail = status.available_replicas or 0
            dep_status = "Healthy" if ready == desired and desired > 0 else (
                "Progressing" if ready < desired and ready > 0 else "Degraded"
            )
            images = [c.image for c in (spec.template.spec.containers or [])]
            result.append(ClusterDeployment(
                name=d.metadata.name,
                namespace=d.metadata.namespace,
                replicas=desired,
                ready_replicas=ready,
                available_replicas=avail,
                image=images[0] if images else None,
                age=_age_from_ts(d.metadata.creation_timestamp),
                status=dep_status,
            ))
        return result

    async def get_services(self, tenant_id: str, cluster_id: str, namespace: Optional[str] = None) -> list[ClusterService]:
        cluster = await self.get_cluster(tenant_id, cluster_id)
        import kubernetes as k8s
        client = self._build_client(cluster)
        if not client:
            return []
        v1 = k8s.client.CoreV1Api(client)
        if namespace:
            resp = v1.list_namespaced_service(namespace)
        else:
            resp = v1.list_service_for_all_namespaces()
        result = []
        for svc in resp.items:
            ports = [
                f"{p.port}/{p.protocol}" + (f":{p.node_port}" if p.node_port else "")
                for p in (svc.spec.ports or [])
            ]
            ext_ip = None
            if svc.status.load_balancer and svc.status.load_balancer.ingress:
                ing = svc.status.load_balancer.ingress[0]
                ext_ip = ing.ip or ing.hostname
            result.append(ClusterService(
                name=svc.metadata.name,
                namespace=svc.metadata.namespace,
                type=svc.spec.type or "ClusterIP",
                cluster_ip=svc.spec.cluster_ip,
                external_ip=ext_ip,
                ports=ports,
                age=_age_from_ts(svc.metadata.creation_timestamp),
            ))
        return result

    async def get_ingresses(self, tenant_id: str, cluster_id: str, namespace: Optional[str] = None) -> list[ClusterIngress]:
        cluster = await self.get_cluster(tenant_id, cluster_id)
        import kubernetes as k8s
        client = self._build_client(cluster)
        if not client:
            return []
        netv1 = k8s.client.NetworkingV1Api(client)
        if namespace:
            resp = netv1.list_namespaced_ingress(namespace)
        else:
            resp = netv1.list_ingress_for_all_namespaces()
        result = []
        for ing in resp.items:
            hosts, paths = [], []
            for rule in (ing.spec.rules or []):
                if rule.host:
                    hosts.append(rule.host)
                if rule.http:
                    for path in (rule.http.paths or []):
                        paths.append(path.path or "/")
            result.append(ClusterIngress(
                name=ing.metadata.name,
                namespace=ing.metadata.namespace,
                class_=ing.spec.ingress_class_name,
                hosts=hosts,
                paths=paths,
                tls=bool(ing.spec.tls),
                age=_age_from_ts(ing.metadata.creation_timestamp),
            ))
        return result

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _build_client(self, cluster: Cluster):
        if cluster.kubeconfig_encrypted:
            try:
                kc_yaml = _decode_kubeconfig(cluster.kubeconfig_encrypted)
                return _get_k8s_client(kc_yaml)
            except Exception as e:
                logger.warning(f"[cluster:client] failed to build client for {cluster.id}: {e}")
                return None
        return _get_default_k8s_client()


# ── Unit conversions ─────────────────────────────────────────────────────────

def _parse_cpu(cpu_str: str) -> float:
    """Parse Kubernetes CPU string to cores (float)."""
    s = str(cpu_str).strip()
    if s.endswith("m"):
        return float(s[:-1]) / 1000
    try:
        return float(s)
    except Exception:
        return 0.0


def _parse_memory(mem_str: str) -> float:
    """Parse Kubernetes memory string to MiB (float)."""
    s = str(mem_str).strip()
    units = {"Ki": 1/1024, "Mi": 1, "Gi": 1024, "Ti": 1024*1024,
             "K": 1/1000, "M": 1, "G": 1000, "T": 1000*1000}
    for suffix, factor in units.items():
        if s.endswith(suffix):
            try:
                return float(s[:-len(suffix)]) * factor
            except Exception:
                return 0.0
    try:
        return float(s) / (1024 * 1024)
    except Exception:
        return 0.0
