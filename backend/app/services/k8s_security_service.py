from __future__ import annotations
"""
Kubernetes Security Scanning Service
=====================================
Orchestrates multiple scanners:
  - Native K8s API checks  (always runs)
  - Kubescape               (if binary available)
  - kube-bench              (if binary available)
  - kube-hunter             (if Python package available)

Detects:
  privileged_containers | rbac | exposed_services |
  network_policy | secrets | cis_benchmark | runtime
"""
import asyncio
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster
from app.models.k8s_security import K8sFinding, K8sScan
from app.utils.logger import logger

# ── Severity weights for risk score ──────────────────────────────────────────
_SEV_WEIGHT = {"critical": 10, "high": 7, "medium": 4, "low": 1, "info": 0}

# ── Sensitive env var patterns ────────────────────────────────────────────────
_SECRET_RE = re.compile(
    r"(password|passwd|secret|token|api[_\-]?key|private[_\-]?key|auth|credential|cert|access[_\-]?key)",
    re.IGNORECASE,
)

# ── Known dangerous ports ────────────────────────────────────────────────────
_DANGEROUS_PORTS = {22, 23, 3389, 6379, 27017, 5432, 3306, 11211, 9200, 2379}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _risk_score(findings: list[dict]) -> float:
    """Weighted risk score 0–100."""
    if not findings:
        return 0.0
    raw = sum(_SEV_WEIGHT.get(f.get("severity", "info"), 0) for f in findings)
    capped = min(raw, 200)
    return round(capped / 2, 1)


# ─── Native K8s API checks ───────────────────────────────────────────────────

class NativeK8sScanner:
    """Uses the kubernetes Python client to run security checks."""

    def __init__(self, cluster: Cluster):
        self.cluster = cluster
        self._client = None
        self._tmpfile: str | None = None

    def _get_k8s(self):
        if self._client:
            return self._client
        try:
            from kubernetes import client as k8s, config as k8s_cfg

            kubeconfig = self.cluster.kubeconfig_encrypted
            if kubeconfig:
                self._tmpfile = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                )
                self._tmpfile.write(kubeconfig)
                self._tmpfile.flush()
                k8s_cfg.load_kube_config(config_file=self._tmpfile.name)
            else:
                k8s_cfg.load_incluster_config()
            self._client = k8s
            return self._client
        except Exception as exc:
            logger.warning(f"[k8s_security] Native client init failed for cluster {self.cluster.id}: {exc}")
            return None

    def cleanup(self):
        if self._tmpfile:
            try:
                os.unlink(self._tmpfile.name)
            except Exception:
                pass

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _list_pods(self, k8s) -> list:
        try:
            v1 = k8s.CoreV1Api()
            return v1.list_pod_for_all_namespaces(watch=False).items
        except Exception as e:
            logger.debug(f"[k8s_security] list_pods: {e}")
            return []

    def _list_namespaces(self, k8s) -> list:
        try:
            v1 = k8s.CoreV1Api()
            return v1.list_namespace(watch=False).items
        except Exception as e:
            logger.debug(f"[k8s_security] list_namespaces: {e}")
            return []

    def _list_services(self, k8s) -> list:
        try:
            v1 = k8s.CoreV1Api()
            return v1.list_service_for_all_namespaces(watch=False).items
        except Exception as e:
            logger.debug(f"[k8s_security] list_services: {e}")
            return []

    def _list_network_policies(self, k8s) -> list:
        try:
            net_v1 = k8s.NetworkingV1Api()
            return net_v1.list_network_policy_for_all_namespaces(watch=False).items
        except Exception as e:
            logger.debug(f"[k8s_security] list_network_policies: {e}")
            return []

    def _list_cluster_role_bindings(self, k8s) -> list:
        try:
            rbac = k8s.RbacAuthorizationV1Api()
            return rbac.list_cluster_role_binding(watch=False).items
        except Exception as e:
            logger.debug(f"[k8s_security] list_crb: {e}")
            return []

    def _list_cluster_roles(self, k8s) -> list:
        try:
            rbac = k8s.RbacAuthorizationV1Api()
            return rbac.list_cluster_role(watch=False).items
        except Exception as e:
            logger.debug(f"[k8s_security] list_cr: {e}")
            return []

    def _list_ingresses(self, k8s) -> list:
        try:
            net_v1 = k8s.NetworkingV1Api()
            return net_v1.list_ingress_for_all_namespaces(watch=False).items
        except Exception as e:
            logger.debug(f"[k8s_security] list_ingress: {e}")
            return []

    def _list_configmaps(self, k8s) -> list:
        try:
            v1 = k8s.CoreV1Api()
            return v1.list_config_map_for_all_namespaces(watch=False).items
        except Exception as e:
            logger.debug(f"[k8s_security] list_configmaps: {e}")
            return []

    # ── Check: Privileged containers ─────────────────────────────────────────

    def check_privileged_containers(self, k8s) -> list[dict]:
        findings: list[dict] = []
        for pod in self._list_pods(k8s):
            meta = pod.metadata
            spec = pod.spec
            ns = meta.namespace
            name = meta.name

            # hostPID / hostIPC / hostNetwork
            for attr, label in [("host_pid", "hostPID"), ("host_ipc", "hostIPC"), ("host_network", "hostNetwork")]:
                if getattr(spec, attr, False):
                    findings.append({
                        "category": "privileged_containers",
                        "severity": "high",
                        "title": f"Pod uses {label}",
                        "description": f"Pod `{name}` in namespace `{ns}` has `{label}: true`. This grants the pod access to the host's process tree, IPC namespace, or network stack.",
                        "remediation": f"Set `spec.{label}` to `false` unless absolutely necessary. Use network policies and RBAC to restrict access instead.",
                        "resource_kind": "Pod",
                        "resource_name": name,
                        "namespace": ns,
                        "cis_control": "5.2.4",
                        "framework": "CIS",
                    })

            for container in (spec.containers or []) + (spec.init_containers or []):
                sc = container.security_context
                if not sc:
                    continue
                if sc.privileged:
                    findings.append({
                        "category": "privileged_containers",
                        "severity": "critical",
                        "title": f"Privileged container: {container.name}",
                        "description": f"Container `{container.name}` in pod `{name}` (ns: `{ns}`) runs with `privileged: true`, giving it full root access to the host.",
                        "remediation": "Set `securityContext.privileged: false`. Use seccomp/AppArmor profiles and drop all capabilities instead.",
                        "resource_kind": "Pod",
                        "resource_name": name,
                        "namespace": ns,
                        "cis_control": "5.2.1",
                        "framework": "CIS",
                        "context": {"container": container.name},
                    })
                if sc.allow_privilege_escalation:
                    findings.append({
                        "category": "privileged_containers",
                        "severity": "high",
                        "title": f"Container allows privilege escalation: {container.name}",
                        "description": f"Container `{container.name}` in pod `{name}` (ns: `{ns}`) has `allowPrivilegeEscalation: true`.",
                        "remediation": "Set `securityContext.allowPrivilegeEscalation: false` on all containers.",
                        "resource_kind": "Pod",
                        "resource_name": name,
                        "namespace": ns,
                        "cis_control": "5.2.5",
                        "framework": "CIS",
                        "context": {"container": container.name},
                    })
                if sc.run_as_user == 0:
                    findings.append({
                        "category": "privileged_containers",
                        "severity": "medium",
                        "title": f"Container runs as root: {container.name}",
                        "description": f"Container `{container.name}` in pod `{name}` (ns: `{ns}`) runs as UID 0 (root).",
                        "remediation": "Set `securityContext.runAsNonRoot: true` and specify a non-zero `runAsUser`.",
                        "resource_kind": "Pod",
                        "resource_name": name,
                        "namespace": ns,
                        "cis_control": "5.2.6",
                        "framework": "CIS",
                        "context": {"container": container.name},
                    })
        return findings

    # ── Check: RBAC misconfigurations ────────────────────────────────────────

    def check_rbac(self, k8s) -> list[dict]:
        findings: list[dict] = []

        # Check ClusterRoles for wildcard rules
        for cr in self._list_cluster_roles(k8s):
            name = cr.metadata.name
            if name.startswith("system:"):
                continue
            for rule in (cr.rules or []):
                verbs = rule.verbs or []
                resources = rule.resources or []
                if "*" in verbs and "*" in resources:
                    findings.append({
                        "category": "rbac",
                        "severity": "critical",
                        "title": f"ClusterRole with wildcard permissions: {name}",
                        "description": f"ClusterRole `{name}` grants `*` verbs on `*` resources — effectively cluster-admin.",
                        "remediation": "Replace wildcard rules with specific, least-privilege permissions.",
                        "resource_kind": "ClusterRole",
                        "resource_name": name,
                        "cis_control": "5.1.3",
                        "framework": "CIS",
                    })
                elif "*" in verbs:
                    findings.append({
                        "category": "rbac",
                        "severity": "high",
                        "title": f"ClusterRole with wildcard verbs: {name}",
                        "description": f"ClusterRole `{name}` grants `*` verbs on resources: {resources}.",
                        "remediation": "Specify explicit verbs (get, list, watch, create, update, delete) instead of `*`.",
                        "resource_kind": "ClusterRole",
                        "resource_name": name,
                        "cis_control": "5.1.2",
                        "framework": "CIS",
                    })

        # Check ClusterRoleBindings for dangerous subjects
        for crb in self._list_cluster_role_bindings(k8s):
            name = crb.metadata.name
            role_ref = crb.role_ref
            subjects = crb.subjects or []

            is_cluster_admin = role_ref.name == "cluster-admin"

            for subj in subjects:
                kind = subj.kind
                subj_name = subj.name

                # Anonymous / unauthenticated
                if subj_name in ("system:anonymous", "system:unauthenticated"):
                    findings.append({
                        "category": "rbac",
                        "severity": "critical",
                        "title": f"Role bound to anonymous/unauthenticated: {name}",
                        "description": f"ClusterRoleBinding `{name}` grants `{role_ref.name}` to `{subj_name}`. This allows unauthenticated access.",
                        "remediation": "Remove this ClusterRoleBinding immediately. Never grant roles to anonymous subjects.",
                        "resource_kind": "ClusterRoleBinding",
                        "resource_name": name,
                        "cis_control": "5.1.5",
                        "framework": "CIS",
                        "context": {"subject": subj_name},
                    })

                # cluster-admin bound to service accounts (non-system)
                if is_cluster_admin and kind == "ServiceAccount":
                    sa_ns = subj.namespace or ""
                    if not (sa_ns.startswith("kube-") or sa_ns == "default"):
                        findings.append({
                            "category": "rbac",
                            "severity": "critical",
                            "title": f"Service account bound to cluster-admin: {subj_name}",
                            "description": f"ServiceAccount `{subj_name}` (ns: `{sa_ns}`) has cluster-admin via ClusterRoleBinding `{name}`.",
                            "remediation": "Remove cluster-admin binding. Create a namespace-scoped Role with minimal permissions.",
                            "resource_kind": "ClusterRoleBinding",
                            "resource_name": name,
                            "cis_control": "5.1.1",
                            "framework": "CIS",
                            "context": {"subject": subj_name, "namespace": sa_ns},
                        })

        return findings

    # ── Check: Exposed services ───────────────────────────────────────────────

    def check_exposed_services(self, k8s) -> list[dict]:
        findings: list[dict] = []

        for svc in self._list_services(k8s):
            meta = svc.metadata
            spec = svc.spec
            name = meta.name
            ns = meta.namespace
            svc_type = spec.type

            if svc_type in ("LoadBalancer", "NodePort"):
                ports = [p.port for p in (spec.ports or [])]
                dangerous = [p for p in ports if p in _DANGEROUS_PORTS]
                severity = "critical" if dangerous else "medium"
                findings.append({
                    "category": "exposed_services",
                    "severity": severity,
                    "title": f"Service exposed externally: {name} ({svc_type})",
                    "description": (
                        f"Service `{name}` (ns: `{ns}`) is of type `{svc_type}` and publicly accessible on ports {ports}."
                        + (f" Dangerous ports exposed: {dangerous}." if dangerous else "")
                    ),
                    "remediation": (
                        "Use internal ClusterIP services where possible. "
                        "Apply NetworkPolicies to restrict access. "
                        "If external access is required, use an Ingress controller with TLS and authentication."
                    ),
                    "resource_kind": "Service",
                    "resource_name": name,
                    "namespace": ns,
                    "cis_control": "5.4.1",
                    "framework": "CIS",
                    "context": {"ports": ports, "type": svc_type},
                })

        # Ingresses without TLS
        for ing in self._list_ingresses(k8s):
            meta = ing.metadata
            spec = ing.spec
            name = meta.name
            ns = meta.namespace
            if not (spec.tls or []):
                findings.append({
                    "category": "exposed_services",
                    "severity": "medium",
                    "title": f"Ingress without TLS: {name}",
                    "description": f"Ingress `{name}` (ns: `{ns}`) does not define a TLS configuration, serving traffic over HTTP.",
                    "remediation": "Add a `tls` block to the Ingress spec. Use cert-manager with Let's Encrypt for automated TLS.",
                    "resource_kind": "Ingress",
                    "resource_name": name,
                    "namespace": ns,
                    "cis_control": "5.4.2",
                    "framework": "CIS",
                })

        return findings

    # ── Check: Network Policy ─────────────────────────────────────────────────

    def check_network_policies(self, k8s) -> list[dict]:
        findings: list[dict] = []

        namespaces = {ns.metadata.name for ns in self._list_namespaces(k8s)}
        policies = self._list_network_policies(k8s)
        covered = {p.metadata.namespace for p in policies}

        system_ns = {"kube-system", "kube-public", "kube-node-lease"}
        unprotected = (namespaces - covered - system_ns)

        for ns in sorted(unprotected):
            findings.append({
                "category": "network_policy",
                "severity": "medium",
                "title": f"Namespace has no NetworkPolicy: {ns}",
                "description": f"Namespace `{ns}` has no NetworkPolicy resources, allowing unrestricted pod-to-pod communication.",
                "remediation": (
                    "Create a default-deny NetworkPolicy for the namespace and add allow rules "
                    "for only the required ingress/egress flows."
                ),
                "resource_kind": "Namespace",
                "resource_name": ns,
                "namespace": ns,
                "cis_control": "5.3.2",
                "framework": "CIS",
            })

        # Check for allow-all policies
        for policy in policies:
            meta = policy.metadata
            spec = policy.spec
            name = meta.name
            ns = meta.namespace
            ingress = spec.ingress or []
            egress = spec.egress or []
            policy_types = spec.policy_types or []

            has_allow_all_ingress = any(
                not rule.from_ for rule in ingress
            ) if ingress else False
            has_allow_all_egress = any(
                not rule.to for rule in egress
            ) if egress else False

            if has_allow_all_ingress:
                findings.append({
                    "category": "network_policy",
                    "severity": "medium",
                    "title": f"NetworkPolicy allows all ingress: {name}",
                    "description": f"NetworkPolicy `{name}` (ns: `{ns}`) has an allow-all ingress rule with no source restrictions.",
                    "remediation": "Replace allow-all ingress with specific pod/namespace selectors.",
                    "resource_kind": "NetworkPolicy",
                    "resource_name": name,
                    "namespace": ns,
                    "cis_control": "5.3.1",
                    "framework": "CIS",
                })

        return findings

    # ── Check: Secrets exposure ───────────────────────────────────────────────

    def check_secrets_exposure(self, k8s) -> list[dict]:
        findings: list[dict] = []

        for pod in self._list_pods(k8s):
            meta = pod.metadata
            spec = pod.spec
            ns = meta.namespace
            name = meta.name

            for container in (spec.containers or []) + (spec.init_containers or []):
                for env in (container.env or []):
                    env_name = env.name or ""
                    if _SECRET_RE.search(env_name) and env.value is not None:
                        findings.append({
                            "category": "secrets",
                            "severity": "high",
                            "title": f"Secret in env var (plaintext): {env_name}",
                            "description": (
                                f"Container `{container.name}` in pod `{name}` (ns: `{ns}`) "
                                f"has env var `{env_name}` with a raw plaintext value. "
                                "Credentials should be stored in Kubernetes Secrets and referenced via `secretKeyRef`."
                            ),
                            "remediation": (
                                "Move the value to a Kubernetes Secret. Reference it using "
                                "`env[].valueFrom.secretKeyRef` instead of a plain `value`."
                            ),
                            "resource_kind": "Pod",
                            "resource_name": name,
                            "namespace": ns,
                            "cis_control": "4.1.6",
                            "framework": "CIS",
                            "context": {"container": container.name, "env_var": env_name},
                        })

        # ConfigMaps with sensitive keys
        for cm in self._list_configmaps(k8s):
            meta = cm.metadata
            ns = meta.namespace
            name = meta.name
            if ns in ("kube-system", "kube-public"):
                continue
            data = cm.data or {}
            for key in data:
                if _SECRET_RE.search(key):
                    findings.append({
                        "category": "secrets",
                        "severity": "medium",
                        "title": f"Sensitive key in ConfigMap: {key}",
                        "description": (
                            f"ConfigMap `{name}` (ns: `{ns}`) contains a key `{key}` that appears to hold sensitive data. "
                            "ConfigMaps are not encrypted at rest and should not store secrets."
                        ),
                        "remediation": "Move this value to a Kubernetes Secret. Enable Secret encryption at rest on the API server.",
                        "resource_kind": "ConfigMap",
                        "resource_name": name,
                        "namespace": ns,
                        "cis_control": "4.1.6",
                        "framework": "CIS",
                        "context": {"key": key},
                    })

        return findings

    # ── Check: CIS Benchmark (what we can check via API) ─────────────────────

    def check_cis_benchmark(self, k8s) -> list[dict]:
        """
        API-checkable CIS controls — control plane config is not accessible
        from inside the cluster, so we check observable cluster behavior.
        """
        findings: list[dict] = []

        # Check: Pods in default namespace (CIS 5.7.2)
        for pod in self._list_pods(k8s):
            if pod.metadata.namespace == "default":
                findings.append({
                    "category": "cis_benchmark",
                    "severity": "low",
                    "title": f"Pod running in default namespace: {pod.metadata.name}",
                    "description": f"Pod `{pod.metadata.name}` is deployed in the `default` namespace. Workloads should use dedicated namespaces.",
                    "remediation": "Create dedicated namespaces for each application and move workloads out of `default`.",
                    "resource_kind": "Pod",
                    "resource_name": pod.metadata.name,
                    "namespace": "default",
                    "cis_control": "5.7.2",
                    "framework": "CIS",
                })

        # Check: Containers without resource limits (CIS 5.2.10)
        for pod in self._list_pods(k8s):
            meta = pod.metadata
            spec = pod.spec
            ns = meta.namespace
            name = meta.name
            for container in (spec.containers or []):
                res = container.resources
                if not res or not res.limits:
                    findings.append({
                        "category": "cis_benchmark",
                        "severity": "low",
                        "title": f"Container without resource limits: {container.name}",
                        "description": f"Container `{container.name}` in pod `{name}` (ns: `{ns}`) has no CPU/memory limits set.",
                        "remediation": "Set `resources.limits.cpu` and `resources.limits.memory` on all containers to prevent resource exhaustion.",
                        "resource_kind": "Pod",
                        "resource_name": name,
                        "namespace": ns,
                        "cis_control": "5.2.10",
                        "framework": "CIS",
                        "context": {"container": container.name},
                    })

        return findings

    def scan(self) -> list[dict]:
        k8s = self._get_k8s()
        if not k8s:
            return []
        findings: list[dict] = []
        try:
            findings += self.check_privileged_containers(k8s)
            findings += self.check_rbac(k8s)
            findings += self.check_exposed_services(k8s)
            findings += self.check_network_policies(k8s)
            findings += self.check_secrets_exposure(k8s)
            findings += self.check_cis_benchmark(k8s)
        except Exception as exc:
            logger.warning(f"[k8s_security] Native scan error: {exc}")
        finally:
            self.cleanup()
        return findings


# ─── External scanner helpers ────────────────────────────────────────────────

async def _run_kubescape(kubeconfig_path: str) -> list[dict]:
    """Run kubescape if installed; parse NSA+MITRE frameworks."""
    try:
        out_file = tempfile.mktemp(suffix=".json")
        proc = await asyncio.create_subprocess_exec(
            "kubescape", "scan", "framework", "nsa,mitre",
            "--kubeconfig", kubeconfig_path,
            "--format", "json",
            "--output", out_file,
            "--verbose",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.communicate(), timeout=120)

        if not os.path.exists(out_file):
            return []

        with open(out_file) as f:
            data = json.load(f)
        os.unlink(out_file)

        findings: list[dict] = []
        for result in data.get("results", []):
            for ctrl in result.get("controls", []):
                status = ctrl.get("status", {}).get("status", "")
                if status not in ("failed", "warning"):
                    continue
                severity_map = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
                sev = severity_map.get(ctrl.get("severity", {}).get("severity", "").lower(), "medium")
                for res in ctrl.get("resources", []):
                    findings.append({
                        "scanner": "kubescape",
                        "category": "cis_benchmark",
                        "severity": sev,
                        "title": ctrl.get("name", "Unknown control"),
                        "description": ctrl.get("description", ""),
                        "remediation": ctrl.get("remediation", ""),
                        "resource_kind": res.get("kind", ""),
                        "resource_name": res.get("name", ""),
                        "namespace": res.get("namespace", ""),
                        "framework": ctrl.get("framework", {}).get("name", ""),
                        "references": [ctrl.get("link", "")],
                    })
        return findings
    except (FileNotFoundError, OSError):
        logger.debug("[k8s_security] kubescape not found, skipping")
        return []
    except asyncio.TimeoutError:
        logger.warning("[k8s_security] kubescape timed out")
        return []
    except Exception as exc:
        logger.warning(f"[k8s_security] kubescape error: {exc}")
        return []


async def _run_kube_bench(kubeconfig_path: str) -> list[dict]:
    """Run kube-bench if installed; parse CIS benchmark results."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "kube-bench", "--json",
            "--kubeconfig", kubeconfig_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        data = json.loads(stdout.decode())

        findings: list[dict] = []
        for group in data.get("Controls", []):
            for test in group.get("tests", []):
                for result in test.get("results", []):
                    if result.get("status") != "FAIL":
                        continue
                    findings.append({
                        "scanner": "kube-bench",
                        "category": "cis_benchmark",
                        "severity": "medium",
                        "title": result.get("desc", "CIS check failed"),
                        "description": result.get("reason", ""),
                        "remediation": result.get("remediation", ""),
                        "cis_control": result.get("test_number", ""),
                        "framework": "CIS",
                        "resource_kind": "Node",
                    })
        return findings
    except (FileNotFoundError, OSError):
        logger.debug("[k8s_security] kube-bench not found, skipping")
        return []
    except asyncio.TimeoutError:
        logger.warning("[k8s_security] kube-bench timed out")
        return []
    except Exception as exc:
        logger.warning(f"[k8s_security] kube-bench error: {exc}")
        return []


async def _run_kube_hunter(target: str) -> list[dict]:
    """Run kube-hunter Python package if installed."""
    try:
        import kube_hunter  # noqa: F401
        from kube_hunter.core.events import handler
        from kube_hunter.modules.hunting import (  # noqa: F401
            arp, cves, dns, etcd, kubelet, mounts, proxy, secrets, version,
        )
        from kube_hunter.core.types import Hunter

        # kube-hunter is complex to run programmatically — use subprocess instead
        proc = await asyncio.create_subprocess_exec(
            "kube-hunter", "--remote", target, "--report", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=90)
        try:
            data = json.loads(stdout.decode())
        except json.JSONDecodeError:
            return []

        findings: list[dict] = []
        for vuln in data.get("vulnerabilities", []):
            sev_map = {"high": "high", "medium": "medium", "low": "low"}
            findings.append({
                "scanner": "kube-hunter",
                "category": "runtime",
                "severity": sev_map.get(vuln.get("severity", "medium").lower(), "medium"),
                "title": vuln.get("vulnerability", "Unknown"),
                "description": vuln.get("description", ""),
                "remediation": vuln.get("evidence", ""),
                "resource_kind": vuln.get("category", ""),
                "resource_name": vuln.get("location", ""),
                "references": [vuln.get("vid", "")],
            })
        return findings
    except ImportError:
        logger.debug("[k8s_security] kube-hunter not installed, skipping")
        return []
    except (FileNotFoundError, OSError):
        logger.debug("[k8s_security] kube-hunter binary not found, skipping")
        return []
    except asyncio.TimeoutError:
        logger.warning("[k8s_security] kube-hunter timed out")
        return []
    except Exception as exc:
        logger.warning(f"[k8s_security] kube-hunter error: {exc}")
        return []


# ─── Main orchestration service ──────────────────────────────────────────────

class K8sSecurityService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_clusters(self, tenant_id: str) -> list[dict]:
        q = select(Cluster).where(Cluster.tenant_id == tenant_id)
        rows = (await self.db.execute(q)).scalars().all()

        result = []
        for c in rows:
            # Latest scan
            scan_q = (
                select(K8sScan)
                .where(K8sScan.cluster_id == c.id, K8sScan.status == "completed")
                .order_by(K8sScan.completed_at.desc())
                .limit(1)
            )
            scan = (await self.db.execute(scan_q)).scalar_one_or_none()

            # Open findings count
            f_count = (await self.db.execute(
                select(func.count()).where(
                    K8sFinding.cluster_id == c.id,
                    K8sFinding.tenant_id == tenant_id,
                    K8sFinding.status == "open",
                )
            )).scalar() or 0

            result.append({
                **c.to_dict(),
                "risk_score": scan.risk_score if scan else None,
                "findings_count": f_count,
                "last_scan": scan.completed_at.isoformat() if scan and scan.completed_at else None,
                "last_scan_id": scan.id if scan else None,
                "scan_status": scan.status if scan else "never",
            })
        return result

    async def get_findings(
        self,
        tenant_id: str,
        cluster_id: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        scan_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        q = select(K8sFinding).where(K8sFinding.tenant_id == tenant_id)
        if cluster_id:
            q = q.where(K8sFinding.cluster_id == cluster_id)
        if category:
            q = q.where(K8sFinding.category == category)
        if severity:
            q = q.where(K8sFinding.severity == severity)
        if status:
            q = q.where(K8sFinding.status == status)
        if scan_id:
            q = q.where(K8sFinding.scan_id == scan_id)

        total_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(total_q)).scalar() or 0

        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        rows = (await self.db.execute(
            q.order_by(K8sFinding.last_seen_at.desc())
             .offset((page - 1) * page_size)
             .limit(page_size)
        )).scalars().all()

        return {
            "data": [f.to_dict() for f in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size),
        }

    async def get_stats(self, tenant_id: str, cluster_id: str | None = None) -> dict:
        base = select(K8sFinding).where(
            K8sFinding.tenant_id == tenant_id,
            K8sFinding.status == "open",
        )
        if cluster_id:
            base = base.where(K8sFinding.cluster_id == cluster_id)

        total = (await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar() or 0

        by_sev = {}
        for sev in ("critical", "high", "medium", "low", "info"):
            cnt = (await self.db.execute(
                select(func.count()).select_from(
                    base.where(K8sFinding.severity == sev).subquery()
                )
            )).scalar() or 0
            by_sev[sev] = cnt

        by_cat_rows = (await self.db.execute(
            select(K8sFinding.category, func.count().label("cnt"))
            .where(K8sFinding.tenant_id == tenant_id, K8sFinding.status == "open")
            .group_by(K8sFinding.category)
        )).all()
        by_cat = {row.category: row.cnt for row in by_cat_rows}

        cluster_count = (await self.db.execute(
            select(func.count()).select_from(
                select(Cluster.id).where(Cluster.tenant_id == tenant_id).subquery()
            )
        )).scalar() or 0

        return {
            "total_findings": total,
            "by_severity": by_sev,
            "by_category": by_cat,
            "cluster_count": cluster_count,
        }

    async def trigger_scan(self, tenant_id: str, cluster_id: str) -> K8sScan:
        """Create a K8sScan record and kick off a background scan."""
        cluster_q = select(Cluster).where(
            Cluster.id == cluster_id, Cluster.tenant_id == tenant_id
        )
        cluster = (await self.db.execute(cluster_q)).scalar_one_or_none()
        if not cluster:
            raise ValueError(f"Cluster {cluster_id} not found")

        scan = K8sScan(
            tenant_id=tenant_id,
            cluster_id=cluster_id,
            status="running",
            started_at=_now(),
        )
        self.db.add(scan)
        await self.db.commit()
        await self.db.refresh(scan)

        # Run async (fire and forget)
        asyncio.create_task(
            self._run_scan(tenant_id, cluster, scan.id)
        )
        return scan

    async def _run_scan(self, tenant_id: str, cluster: Cluster, scan_id: str) -> None:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            try:
                await self._do_scan(db, tenant_id, cluster, scan_id)
            except Exception as exc:
                logger.error(f"[k8s_security] Scan {scan_id} failed: {exc}")
                scan = await db.get(K8sScan, scan_id)
                if scan:
                    scan.status = "failed"
                    scan.error_message = str(exc)
                    scan.completed_at = _now()
                    await db.commit()

    async def _do_scan(self, db: AsyncSession, tenant_id: str, cluster: Cluster, scan_id: str) -> None:
        logger.info(f"[k8s_security] Starting scan {scan_id} for cluster {cluster.id}")
        all_findings: list[dict] = []
        scanners_run: list[str] = []

        # 1. Native K8s API checks
        native = NativeK8sScanner(cluster)
        native_results = await asyncio.get_event_loop().run_in_executor(None, native.scan)
        if native_results is not None:
            for f in native_results:
                f.setdefault("scanner", "native")
            all_findings += native_results
            scanners_run.append("native")

        # 2. External scanners — only if cluster has kubeconfig
        kubeconfig = cluster.kubeconfig_encrypted
        if kubeconfig:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
            try:
                tmp.write(kubeconfig)
                tmp.flush()
                kc_path = tmp.name

                # Kubescape
                ks_results = await _run_kubescape(kc_path)
                if ks_results:
                    all_findings += ks_results
                    scanners_run.append("kubescape")

                # kube-bench
                kb_results = await _run_kube_bench(kc_path)
                if kb_results:
                    all_findings += kb_results
                    scanners_run.append("kube-bench")
            finally:
                tmp.close()
                os.unlink(tmp.name)

        # 3. kube-hunter (uses API server URL)
        if cluster.api_server_url:
            kh_results = await _run_kube_hunter(cluster.api_server_url)
            if kh_results:
                all_findings += kh_results
                scanners_run.append("kube-hunter")

        # Persist findings
        now = _now()
        for raw in all_findings:
            # Deduplicate by (cluster, title, resource_name, namespace)
            dedup_q = select(K8sFinding).where(
                K8sFinding.cluster_id == cluster.id,
                K8sFinding.tenant_id == tenant_id,
                K8sFinding.title == raw.get("title", ""),
                K8sFinding.resource_name == raw.get("resource_name"),
                K8sFinding.namespace == raw.get("namespace"),
                K8sFinding.status != "resolved",
            )
            existing = (await db.execute(dedup_q)).scalar_one_or_none()

            if existing:
                existing.last_seen_at = now
                existing.scan_id = scan_id
                existing.description = raw.get("description", existing.description)
            else:
                finding = K8sFinding(
                    tenant_id=tenant_id,
                    cluster_id=cluster.id,
                    scan_id=scan_id,
                    scanner=raw.get("scanner", "native"),
                    category=raw.get("category", "cis_benchmark"),
                    severity=raw.get("severity", "medium"),
                    title=raw.get("title", ""),
                    description=raw.get("description"),
                    remediation=raw.get("remediation"),
                    references=raw.get("references", []),
                    resource_kind=raw.get("resource_kind"),
                    resource_name=raw.get("resource_name"),
                    namespace=raw.get("namespace"),
                    context=raw.get("context", {}),
                    cis_control=raw.get("cis_control"),
                    framework=raw.get("framework"),
                    status="open",
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(finding)

        # Update scan record
        scan = await db.get(K8sScan, scan_id)
        if scan:
            scan.status = "completed"
            scan.completed_at = now
            scan.scanners_run = scanners_run
            scan.risk_score = _risk_score(all_findings)
            scan.findings_count = len(all_findings)
            scan.critical_count = sum(1 for f in all_findings if f.get("severity") == "critical")
            scan.high_count     = sum(1 for f in all_findings if f.get("severity") == "high")
            scan.medium_count   = sum(1 for f in all_findings if f.get("severity") == "medium")
            scan.low_count      = sum(1 for f in all_findings if f.get("severity") == "low")
            scan.info_count     = sum(1 for f in all_findings if f.get("severity") == "info")

        await db.commit()
        logger.info(f"[k8s_security] Scan {scan_id} completed: {len(all_findings)} findings, risk={scan.risk_score if scan else 0}")

    async def get_scan_history(self, tenant_id: str, cluster_id: str, limit: int = 10) -> list[dict]:
        q = (
            select(K8sScan)
            .where(K8sScan.tenant_id == tenant_id, K8sScan.cluster_id == cluster_id)
            .order_by(K8sScan.created_at.desc())
            .limit(limit)
        )
        rows = (await self.db.execute(q)).scalars().all()
        return [r.to_dict() for r in rows]

    async def suppress_finding(self, tenant_id: str, finding_id: str) -> K8sFinding:
        f = await self.db.get(K8sFinding, finding_id)
        if not f or f.tenant_id != tenant_id:
            raise ValueError("Finding not found")
        f.status = "suppressed"
        f.suppressed = True
        await self.db.commit()
        return f

    async def resolve_finding(self, tenant_id: str, finding_id: str) -> K8sFinding:
        f = await self.db.get(K8sFinding, finding_id)
        if not f or f.tenant_id != tenant_id:
            raise ValueError("Finding not found")
        f.status = "resolved"
        f.resolved_at = _now()
        await self.db.commit()
        return f
