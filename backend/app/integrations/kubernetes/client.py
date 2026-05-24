from __future__ import annotations
"""Kubernetes client — connects via kubeconfig file or in-cluster config."""
import tempfile, os
from app.integrations.base import BaseIntegration
from app.utils.logger import logger


def _parse_cpu(cpu_str: str | None) -> float | None:
    """Convert '125m' → 0.125 cores, '2' → 2.0 cores."""
    if not cpu_str:
        return None
    try:
        if cpu_str.endswith("m"):
            return round(int(cpu_str[:-1]) / 1000, 4)
        return float(cpu_str)
    except (ValueError, TypeError):
        return None


def _parse_memory(mem_str: str | None) -> int | None:
    """Convert '256Mi' → bytes as int."""
    if not mem_str:
        return None
    try:
        units = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4,
                 "K": 1000, "M": 1000**2, "G": 1000**3}
        for suffix, multiplier in units.items():
            if mem_str.endswith(suffix):
                return int(float(mem_str[:-len(suffix)]) * multiplier)
        return int(mem_str)
    except (ValueError, TypeError):
        return None


class KubernetesClient(BaseIntegration):
    def __init__(self, config: dict):
        super().__init__(config)
        self._k8s_client = None
        self._kubeconfig_file = None

    def _get_client(self):
        if self._k8s_client:
            return self._k8s_client
        try:
            from kubernetes import client as k8s_client, config as k8s_config

            kubeconfig_content = self.config.get("kubeconfig_content") or self.config.get("kubeconfig")
            kubeconfig_path    = self.config.get("kubeconfig_path")

            if kubeconfig_content and isinstance(kubeconfig_content, str):
                # Write temp file from stored content
                self._kubeconfig_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                )
                self._kubeconfig_file.write(kubeconfig_content)
                self._kubeconfig_file.flush()
                k8s_config.load_kube_config(config_file=self._kubeconfig_file.name)

            elif kubeconfig_path and os.path.exists(kubeconfig_path):
                k8s_config.load_kube_config(config_file=kubeconfig_path)

            else:
                # Try in-cluster config (running inside a pod)
                k8s_config.load_incluster_config()

            self._k8s_client = k8s_client
            return self._k8s_client

        except Exception as e:
            logger.warning(f"K8s client init failed: {e}")
            return None

    def __del__(self):
        """Clean up temp kubeconfig file."""
        if self._kubeconfig_file:
            try:
                os.unlink(self._kubeconfig_file.name)
            except Exception:
                pass

    async def test_connection(self) -> bool:
        try:
            k8s = self._get_client()
            if not k8s:
                return False
            v1 = k8s.CoreV1Api()
            v1.list_namespace(_request_timeout=5)
            return True
        except Exception as e:
            logger.warning(f"K8s connection test failed: {e}")
            return False

    async def get_namespaces(self) -> list[str]:
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            v1 = k8s.CoreV1Api()
            ns_list = v1.list_namespace(_request_timeout=10)
            return [ns.metadata.name for ns in ns_list.items]
        except Exception as e:
            logger.warning(f"K8s get_namespaces failed: {e}")
            return []

    async def list_pods(self, namespace: str = "default") -> list[dict]:
        """List all pods in a namespace with full details."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            v1 = k8s.CoreV1Api()
            pod_list = v1.list_namespaced_pod(namespace, _request_timeout=15)

            result = []
            for p in pod_list.items:
                meta = p.metadata
                spec = p.spec
                status = p.status

                # Count restarts across all containers
                restart_count = 0
                containers_info = []
                for cs in (status.container_statuses or []):
                    restart_count += cs.restart_count or 0
                    state = "running" if cs.state.running else ("terminated" if cs.state.terminated else "waiting")
                    containers_info.append({
                        "name": cs.name,
                        "ready": cs.ready,
                        "restarts": cs.restart_count,
                        "state": state,
                        "image": cs.image,
                    })

                # Resource requests/limits from first container
                cpu_req = cpu_lim = mem_req = mem_lim = None
                if spec.containers:
                    c = spec.containers[0]
                    if c.resources:
                        req = c.resources.requests or {}
                        lim = c.resources.limits or {}
                        cpu_req = _parse_cpu(req.get("cpu"))
                        cpu_lim = _parse_cpu(lim.get("cpu"))
                        mem_req = _parse_memory(req.get("memory"))
                        mem_lim = _parse_memory(lim.get("memory"))

                result.append({
                    "name": meta.name,
                    "namespace": meta.namespace,
                    "node": spec.node_name,
                    "status": status.phase or "Unknown",
                    "phase": status.phase,
                    "restart_count": restart_count,
                    "cpu_request": cpu_req,
                    "cpu_limit": cpu_lim,
                    "memory_request": mem_req,
                    "memory_limit": mem_lim,
                    "containers": containers_info,
                    "labels": dict(meta.labels or {}),
                    "created_at": meta.creation_timestamp.isoformat() if meta.creation_timestamp else None,
                    "conditions": [
                        {"type": c.type, "status": c.status}
                        for c in (status.conditions or [])
                    ],
                })
            return result

        except Exception as e:
            logger.warning(f"K8s list_pods({namespace}) failed: {e}")
            return []

    async def list_all_pods(self) -> list[dict]:
        """List pods across ALL namespaces."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            v1 = k8s.CoreV1Api()
            pod_list = v1.list_pod_for_all_namespaces(_request_timeout=20)

            result = []
            for p in pod_list.items:
                meta = p.metadata
                spec = p.spec
                status = p.status

                restart_count = sum(
                    (cs.restart_count or 0) for cs in (status.container_statuses or [])
                )
                containers_info = [
                    {
                        "name": cs.name,
                        "ready": cs.ready,
                        "restarts": cs.restart_count,
                        "state": "running" if cs.state.running else ("terminated" if cs.state.terminated else "waiting"),
                        "image": cs.image,
                    }
                    for cs in (status.container_statuses or [])
                ]

                cpu_req = cpu_lim = mem_req = mem_lim = None
                if spec.containers:
                    c = spec.containers[0]
                    if c.resources:
                        req = c.resources.requests or {}
                        lim = c.resources.limits or {}
                        cpu_req = _parse_cpu(req.get("cpu"))
                        cpu_lim = _parse_cpu(lim.get("cpu"))
                        mem_req = _parse_memory(req.get("memory"))
                        mem_lim = _parse_memory(lim.get("memory"))

                result.append({
                    "name": meta.name,
                    "namespace": meta.namespace or "default",
                    "node": spec.node_name,
                    "status": status.phase or "Unknown",
                    "phase": status.phase,
                    "restart_count": restart_count,
                    "cpu_request": cpu_req,
                    "cpu_limit": cpu_lim,
                    "memory_request": mem_req,
                    "memory_limit": mem_lim,
                    "containers": containers_info,
                    "labels": dict(meta.labels or {}),
                })
            return result

        except Exception as e:
            logger.warning(f"K8s list_all_pods failed: {e}")
            return []

    async def get_node_metrics(self) -> list[dict]:
        """Get node-level CPU/memory usage via metrics-server."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            custom = k8s.CustomObjectsApi()
            nodes = custom.list_cluster_custom_object(
                "metrics.k8s.io", "v1beta1", "nodes", _request_timeout=10
            )
            result = []
            for n in nodes.get("items", []):
                usage = n.get("usage", {})
                result.append({
                    "name": n["metadata"]["name"],
                    "cpu_usage": _parse_cpu(usage.get("cpu")),
                    "memory_usage": _parse_memory(usage.get("memory")),
                })
            return result
        except Exception:
            return []   # metrics-server may not be installed

    async def get_pod_metrics(self, namespace: str = None) -> dict[str, dict]:
        """Get pod CPU/memory usage via metrics-server. Returns {pod_name: {cpu, memory}}."""
        try:
            k8s = self._get_client()
            if not k8s:
                return {}
            custom = k8s.CustomObjectsApi()
            if namespace:
                items = custom.list_namespaced_custom_object(
                    "metrics.k8s.io", "v1beta1", namespace, "pods", _request_timeout=10
                ).get("items", [])
            else:
                items = custom.list_cluster_custom_object(
                    "metrics.k8s.io", "v1beta1", "pods", _request_timeout=10
                ).get("items", [])

            result = {}
            for pm in items:
                name = pm["metadata"]["name"]
                containers = pm.get("containers", [{}])
                cpu = sum(_parse_cpu(c.get("usage", {}).get("cpu")) or 0 for c in containers)
                mem = sum(_parse_memory(c.get("usage", {}).get("memory")) or 0 for c in containers)
                result[name] = {"cpu_usage": cpu, "memory_usage": mem}
            return result
        except Exception:
            return {}   # metrics-server not available

    async def delete_pod(self, name: str, namespace: str) -> dict:
        """
        Delete a pod from the cluster.
        Kubernetes will recreate it automatically if it belongs to a Deployment/ReplicaSet.
        """
        try:
            k8s = self._get_client()
            if not k8s:
                return {"success": False, "error": "Kubernetes client unavailable"}

            v1 = k8s.CoreV1Api()
            # V1DeleteOptions — import from kubernetes.client directly (v29 compatible)
            delete_opts = k8s.V1DeleteOptions(grace_period_seconds=0)
            v1.delete_namespaced_pod(
                name=name,
                namespace=namespace,
                body=delete_opts,
                _request_timeout=15,
            )
            logger.info(f"Pod deleted from cluster: {namespace}/{name}")
            return {"success": True, "name": name, "namespace": namespace}

        except Exception as e:
            err = str(e)
            if hasattr(e, "body"):
                import json as _json
                try:
                    body = _json.loads(e.body)
                    err = body.get("message", err)
                except Exception:
                    pass
            logger.error(f"K8s delete_pod failed ({namespace}/{name}): {err}")
            return {"success": False, "error": err}

    async def restart_pod(self, name: str, namespace: str) -> dict:
        """
        Graceful restart: delete the pod (grace_period=30s).
        The controller (Deployment/StatefulSet) reschedules it immediately.
        """
        try:
            k8s = self._get_client()
            if not k8s:
                return {"success": False, "error": "Kubernetes client unavailable"}

            v1 = k8s.CoreV1Api()

            # Verify pod exists and get owner references
            try:
                pod_obj = v1.read_namespaced_pod(
                    name=name, namespace=namespace, _request_timeout=10
                )
            except Exception:
                return {"success": False, "error": f"Pod {name} not found in namespace {namespace}"}

            owner_refs = pod_obj.metadata.owner_references or []
            has_controller = any(ref.controller for ref in owner_refs if ref.controller)

            if not has_controller:
                logger.warning(f"Pod {namespace}/{name} has no controller — restart = delete without recreation")

            delete_opts = k8s.V1DeleteOptions(grace_period_seconds=30)
            v1.delete_namespaced_pod(
                name=name,
                namespace=namespace,
                body=delete_opts,
                _request_timeout=15,
            )
            logger.info(f"Pod restart initiated: {namespace}/{name} (has_controller={has_controller})")
            return {
                "success":        True,
                "name":           name,
                "namespace":      namespace,
                "has_controller": has_controller,
                "message": (
                    "Pod deleted — controller will reschedule it"
                    if has_controller
                    else "Standalone pod deleted (no controller to reschedule)"
                ),
            }

        except Exception as e:
            err = str(e)
            if hasattr(e, "body"):
                import json as _json
                try:
                    body = _json.loads(e.body)
                    err = body.get("message", err)
                except Exception:
                    pass
            logger.error(f"K8s restart_pod failed ({namespace}/{name}): {err}")
            return {"success": False, "error": err}

    async def get_pod_events(self, name: str, namespace: str) -> list[dict]:
        """Fetch recent K8s events for a specific pod."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            v1 = k8s.CoreV1Api()
            events = v1.list_namespaced_event(
                namespace=namespace,
                field_selector=f"involvedObject.name={name}",
                _request_timeout=10,
            )
            return [
                {
                    "type":       e.type,
                    "reason":     e.reason,
                    "message":    e.message,
                    "count":      e.count,
                    "first_time": e.first_timestamp.isoformat() if e.first_timestamp else None,
                    "last_time":  e.last_timestamp.isoformat()  if e.last_timestamp  else None,
                }
                for e in sorted(
                    events.items,
                    key=lambda x: x.last_timestamp or x.first_timestamp,
                    reverse=True,
                )[:20]
            ]
        except Exception as e:
            logger.warning(f"K8s get_pod_events failed ({namespace}/{name}): {e}")
            return []

    async def sync(self) -> dict:
        """Sync all pods across all namespaces."""
        pods = await self.list_all_pods()
        namespaces = list({p["namespace"] for p in pods})
        return {"pods": len(pods), "namespaces": len(namespaces)}

    async def exec_pod(
        self,
        name: str,
        namespace: str,
        command: str,
        container: str | None = None,
    ) -> str:
        """Execute a command in a running pod via kubernetes exec API."""
        try:
            k8s = self._get_client()
            if not k8s:
                return "Kubernetes client unavailable"

            from kubernetes.stream import stream as k8s_stream

            kwargs: dict = dict(
                name=name,
                namespace=namespace,
                command=["/bin/sh", "-c", command],
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _request_timeout=15,
            )
            if container:
                kwargs["container"] = container

            v1     = k8s.CoreV1Api()
            output = k8s_stream(v1.connect_get_namespaced_pod_exec, **kwargs)
            return output if output else "(no output)"

        except Exception as e:
            logger.warning(f"K8s exec_pod failed ({namespace}/{name}): {e}")
            return f"exec failed: {e}"

    async def scale_deployment(
        self,
        name: str,
        namespace: str,
        replicas: int,
    ) -> dict:
        """Scale a Kubernetes Deployment to the specified replica count."""
        try:
            k8s = self._get_client()
            if not k8s:
                return {"success": False, "error": "Kubernetes client unavailable"}

            apps_v1 = k8s.AppsV1Api()
            body    = {"spec": {"replicas": replicas}}
            apps_v1.patch_namespaced_deployment_scale(
                name=name,
                namespace=namespace,
                body=body,
                _request_timeout=15,
            )
            logger.info(f"Deployment scaled: {namespace}/{name} → {replicas} replicas")
            return {
                "success":    True,
                "name":       name,
                "namespace":  namespace,
                "replicas":   replicas,
                "message":    f"Deployment {name} scaled to {replicas} replica(s)",
            }

        except Exception as e:
            err = str(e)
            if hasattr(e, "body"):
                import json as _j
                try:
                    err = _j.loads(e.body).get("message", err)
                except Exception:
                    pass
            logger.error(f"K8s scale_deployment failed ({namespace}/{name}): {err}")
            return {"success": False, "error": err}

    # ══════════════════════════════════════════════════════════════════════════
    # CLUSTER-LEVEL VISIBILITY — Deployments, Services, HPA, Jobs, ConfigMaps
    # ══════════════════════════════════════════════════════════════════════════

    async def list_deployments(self, namespace: str | None = None) -> list[dict]:
        """List Deployments across all namespaces or a specific one."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            apps = k8s.AppsV1Api()
            if namespace:
                items = apps.list_namespaced_deployment(namespace, _request_timeout=15).items
            else:
                items = apps.list_deployment_for_all_namespaces(_request_timeout=15).items

            result = []
            for d in items:
                spec   = d.spec
                status = d.status
                result.append({
                    "name":               d.metadata.name,
                    "namespace":          d.metadata.namespace,
                    "replicas":           spec.replicas or 0,
                    "ready_replicas":     status.ready_replicas or 0,
                    "available_replicas": status.available_replicas or 0,
                    "updated_replicas":   status.updated_replicas or 0,
                    "strategy":           spec.strategy.type if spec.strategy else "RollingUpdate",
                    "images":             [c.image for c in spec.template.spec.containers],
                    "labels":             dict(d.metadata.labels or {}),
                    "selector":           dict(spec.selector.match_labels or {}),
                    "created_at":         d.metadata.creation_timestamp.isoformat() if d.metadata.creation_timestamp else None,
                    "conditions": [
                        {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
                        for c in (status.conditions or [])
                    ],
                })
            return result
        except Exception as e:
            logger.warning(f"K8s list_deployments failed: {e}")
            return []

    async def list_statefulsets(self, namespace: str | None = None) -> list[dict]:
        """List StatefulSets."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            apps = k8s.AppsV1Api()
            if namespace:
                items = apps.list_namespaced_stateful_set(namespace, _request_timeout=15).items
            else:
                items = apps.list_stateful_set_for_all_namespaces(_request_timeout=15).items

            return [{
                "name":           d.metadata.name,
                "namespace":      d.metadata.namespace,
                "replicas":       d.spec.replicas or 0,
                "ready_replicas": d.status.ready_replicas or 0,
                "service_name":   d.spec.service_name,
                "images":         [c.image for c in d.spec.template.spec.containers],
                "labels":         dict(d.metadata.labels or {}),
                "created_at":     d.metadata.creation_timestamp.isoformat() if d.metadata.creation_timestamp else None,
            } for d in items]
        except Exception as e:
            logger.warning(f"K8s list_statefulsets failed: {e}")
            return []

    async def list_daemonsets(self, namespace: str | None = None) -> list[dict]:
        """List DaemonSets."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            apps = k8s.AppsV1Api()
            if namespace:
                items = apps.list_namespaced_daemon_set(namespace, _request_timeout=15).items
            else:
                items = apps.list_daemon_set_for_all_namespaces(_request_timeout=15).items

            return [{
                "name":                   d.metadata.name,
                "namespace":              d.metadata.namespace,
                "desired_number_scheduled": d.status.desired_number_scheduled or 0,
                "number_ready":           d.status.number_ready or 0,
                "number_available":       d.status.number_available or 0,
                "images":                 [c.image for c in d.spec.template.spec.containers],
                "labels":                 dict(d.metadata.labels or {}),
                "created_at":             d.metadata.creation_timestamp.isoformat() if d.metadata.creation_timestamp else None,
            } for d in items]
        except Exception as e:
            logger.warning(f"K8s list_daemonsets failed: {e}")
            return []

    async def list_services(self, namespace: str | None = None) -> list[dict]:
        """List Services (ClusterIP, NodePort, LoadBalancer)."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            v1 = k8s.CoreV1Api()
            if namespace:
                items = v1.list_namespaced_service(namespace, _request_timeout=15).items
            else:
                items = v1.list_service_for_all_namespaces(_request_timeout=15).items

            result = []
            for s in items:
                spec = s.spec
                # Extract external IPs / LoadBalancer hostname
                external_ip = None
                if s.status.load_balancer and s.status.load_balancer.ingress:
                    ingress = s.status.load_balancer.ingress[0]
                    external_ip = ingress.ip or ingress.hostname

                result.append({
                    "name":         s.metadata.name,
                    "namespace":    s.metadata.namespace,
                    "type":         spec.type,
                    "cluster_ip":   spec.cluster_ip,
                    "external_ip":  external_ip,
                    "ports": [
                        {
                            "port":        p.port,
                            "target_port": str(p.target_port),
                            "protocol":    p.protocol,
                            "node_port":   p.node_port,
                        }
                        for p in (spec.ports or [])
                    ],
                    "selector":   dict(spec.selector or {}),
                    "created_at": s.metadata.creation_timestamp.isoformat() if s.metadata.creation_timestamp else None,
                })
            return result
        except Exception as e:
            logger.warning(f"K8s list_services failed: {e}")
            return []

    async def list_ingresses(self, namespace: str | None = None) -> list[dict]:
        """List Ingresses (networking.k8s.io/v1)."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            net = k8s.NetworkingV1Api()
            if namespace:
                items = net.list_namespaced_ingress(namespace, _request_timeout=15).items
            else:
                items = net.list_ingress_for_all_namespaces(_request_timeout=15).items

            result = []
            for ing in items:
                rules = []
                for rule in (ing.spec.rules or []):
                    host = rule.host or "*"
                    paths = []
                    if rule.http:
                        for path in (rule.http.paths or []):
                            backend = path.backend
                            svc = backend.service
                            paths.append({
                                "path":    path.path,
                                "service": svc.name if svc else None,
                                "port":    svc.port.number if svc and svc.port else None,
                            })
                    rules.append({"host": host, "paths": paths})

                result.append({
                    "name":       ing.metadata.name,
                    "namespace":  ing.metadata.namespace,
                    "class_name": ing.spec.ingress_class_name,
                    "rules":      rules,
                    "tls":        [{"hosts": t.hosts, "secret": t.secret_name} for t in (ing.spec.tls or [])],
                    "created_at": ing.metadata.creation_timestamp.isoformat() if ing.metadata.creation_timestamp else None,
                })
            return result
        except Exception as e:
            logger.warning(f"K8s list_ingresses failed: {e}")
            return []

    async def list_jobs(self, namespace: str | None = None) -> list[dict]:
        """List Jobs and CronJobs."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            batch = k8s.BatchV1Api()

            # Regular Jobs
            if namespace:
                jobs    = batch.list_namespaced_job(namespace, _request_timeout=15).items
                cronjobs= batch.list_namespaced_cron_job(namespace, _request_timeout=15).items
            else:
                jobs    = batch.list_job_for_all_namespaces(_request_timeout=15).items
                cronjobs= batch.list_cron_job_for_all_namespaces(_request_timeout=15).items

            result = []
            for j in jobs:
                status = j.status
                result.append({
                    "kind":         "Job",
                    "name":         j.metadata.name,
                    "namespace":    j.metadata.namespace,
                    "active":       status.active or 0,
                    "succeeded":    status.succeeded or 0,
                    "failed":       status.failed or 0,
                    "completions":  j.spec.completions,
                    "start_time":   status.start_time.isoformat() if status.start_time else None,
                    "completion_time": status.completion_time.isoformat() if status.completion_time else None,
                    "labels":       dict(j.metadata.labels or {}),
                })

            for cj in cronjobs:
                result.append({
                    "kind":        "CronJob",
                    "name":        cj.metadata.name,
                    "namespace":   cj.metadata.namespace,
                    "schedule":    cj.spec.schedule,
                    "suspended":   cj.spec.suspend or False,
                    "active_jobs": len(cj.status.active or []),
                    "last_run":    cj.status.last_schedule_time.isoformat() if cj.status.last_schedule_time else None,
                    "labels":      dict(cj.metadata.labels or {}),
                })

            return result
        except Exception as e:
            logger.warning(f"K8s list_jobs failed: {e}")
            return []

    async def list_configmaps(self, namespace: str | None = None) -> list[dict]:
        """List ConfigMaps (keys only — never values for security)."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            v1 = k8s.CoreV1Api()
            if namespace:
                items = v1.list_namespaced_config_map(namespace, _request_timeout=15).items
            else:
                items = v1.list_config_map_for_all_namespaces(_request_timeout=15).items

            # Filter out system configmaps
            return [
                {
                    "name":       cm.metadata.name,
                    "namespace":  cm.metadata.namespace,
                    "keys":       list((cm.data or {}).keys()),   # keys only — never values
                    "key_count":  len(cm.data or {}),
                    "labels":     dict(cm.metadata.labels or {}),
                    "created_at": cm.metadata.creation_timestamp.isoformat() if cm.metadata.creation_timestamp else None,
                }
                for cm in items
                if not cm.metadata.name.startswith("kube-")  # skip system CMs
            ]
        except Exception as e:
            logger.warning(f"K8s list_configmaps failed: {e}")
            return []

    async def list_secrets_metadata(self, namespace: str | None = None) -> list[dict]:
        """List Secrets — METADATA ONLY, never values (security requirement)."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            v1 = k8s.CoreV1Api()
            if namespace:
                items = v1.list_namespaced_secret(namespace, _request_timeout=15).items
            else:
                items = v1.list_secret_for_all_namespaces(_request_timeout=15).items

            # NEVER expose secret values — metadata only
            return [
                {
                    "name":       s.metadata.name,
                    "namespace":  s.metadata.namespace,
                    "type":       s.type,
                    "keys":       list((s.data or {}).keys()),   # key names only
                    "key_count":  len(s.data or {}),
                    "labels":     dict(s.metadata.labels or {}),
                    "created_at": s.metadata.creation_timestamp.isoformat() if s.metadata.creation_timestamp else None,
                    # ⚠️ values intentionally omitted
                }
                for s in items
                if s.type != "kubernetes.io/service-account-token"  # skip auto-generated
            ]
        except Exception as e:
            logger.warning(f"K8s list_secrets_metadata failed: {e}")
            return []

    async def list_hpa(self, namespace: str | None = None) -> list[dict]:
        """List Horizontal Pod Autoscalers."""
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            autoscaling = k8s.AutoscalingV2Api()
            if namespace:
                items = autoscaling.list_namespaced_horizontal_pod_autoscaler(namespace, _request_timeout=15).items
            else:
                items = autoscaling.list_horizontal_pod_autoscaler_for_all_namespaces(_request_timeout=15).items

            result = []
            for hpa in items:
                spec   = hpa.spec
                status = hpa.status
                metrics_info = []
                for m in (spec.metrics or []):
                    if m.type == "Resource" and m.resource:
                        target = m.resource.target
                        metrics_info.append({
                            "type":       m.type,
                            "resource":   m.resource.name,
                            "target_type":  target.type,
                            "target_value": target.average_utilization or target.average_value,
                        })

                result.append({
                    "name":              hpa.metadata.name,
                    "namespace":         hpa.metadata.namespace,
                    "target_kind":       spec.scale_target_ref.kind,
                    "target_name":       spec.scale_target_ref.name,
                    "min_replicas":      spec.min_replicas or 1,
                    "max_replicas":      spec.max_replicas,
                    "current_replicas":  status.current_replicas or 0,
                    "desired_replicas":  status.desired_replicas or 0,
                    "current_cpu_pct":   status.current_metrics[0].resource.current.average_utilization
                                         if (status.current_metrics and status.current_metrics[0].resource) else None,
                    "metrics":           metrics_info,
                    "conditions": [
                        {"type": c.type, "status": c.status, "reason": c.reason}
                        for c in (status.conditions or [])
                    ],
                    "created_at": hpa.metadata.creation_timestamp.isoformat() if hpa.metadata.creation_timestamp else None,
                })
            return result
        except Exception as e:
            logger.warning(f"K8s list_hpa failed: {e}")
            return []

    async def watch_cluster_events(self, namespace: str | None = None, timeout: int = 30) -> list[dict]:
        """
        Watch real-time cluster events for a short window.
        Returns events collected during the timeout period.
        Used by WebSocket endpoint to push live updates.
        """
        import asyncio
        from kubernetes import watch as k8s_watch
        try:
            k8s = self._get_client()
            if not k8s:
                return []
            v1      = k8s.CoreV1Api()
            watcher = k8s_watch.Watch()
            events  = []

            def _collect():
                fn = v1.list_namespaced_event if namespace else v1.list_event_for_all_namespaces
                kwargs = {"_request_timeout": timeout, "timeout_seconds": timeout}
                if namespace:
                    kwargs["namespace"] = namespace
                for evt in watcher.stream(fn, **kwargs):
                    obj = evt["object"]
                    events.append({
                        "event_type": evt["type"],        # ADDED | MODIFIED | DELETED
                        "type":       obj.type,           # Normal | Warning
                        "reason":     obj.reason,
                        "message":    obj.message,
                        "namespace":  obj.metadata.namespace,
                        "name":       obj.metadata.name,
                        "involved":   obj.involved_object.name if obj.involved_object else None,
                        "kind":       obj.involved_object.kind if obj.involved_object else None,
                        "timestamp":  obj.last_timestamp.isoformat() if obj.last_timestamp else None,
                    })
                    if len(events) >= 50:  # cap at 50 events per watch window
                        watcher.stop()

            # Run blocking watch in thread pool
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, _collect),
                timeout=timeout + 1,
            )
            return events

        except asyncio.TimeoutError:
            return events if 'events' in dir() else []
        except Exception as e:
            logger.warning(f"K8s watch_cluster_events failed: {e}")
            return []
