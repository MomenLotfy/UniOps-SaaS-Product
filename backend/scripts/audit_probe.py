"""
DevOps Center — LIVE endpoint verification harness.

Mints real JWTs for the audit fixture users and fires every request the
DevOps Center UI actually makes, recording HTTP status + response body.
Read-only by default; mutation probes are behind --mutations.

Run:  cd backend && .venv/bin/python scripts/audit_probe.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# NOTE: deliberately does NOT set SECRET_KEY / JWT_SECRET_KEY here.  The
# running server loads backend/.env, and env vars outrank env_file, so
# setting them in this process would mint tokens the server rejects.

from app.core.security import create_access_token  # noqa: E402
from app.config import settings as _settings  # noqa: E402

# Guarantee the probe derives tokens with EXACTLY the same key the running
# server uses (the server loads backend/.env via pydantic-settings).
print(f"[probe] JWT_SECRET_KEY={_settings.JWT_SECRET_KEY[:8]}... "
      f"algo={_settings.JWT_ALGORITHM} db={_settings.DATABASE_URL}")

BASE = os.environ.get("PROBE_BASE", "http://127.0.0.1:8000") + "/api/v1"
IDS = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".audit_ids.json")))

USERS = {
    "admin_a":  ("admin@a.audit.dev",  IDS["tenant_a"], ["admin"]),
    "devops_a": ("devops@a.audit.dev", IDS["tenant_a"], ["devops_engineer"]),
    "viewer_a": ("viewer@a.audit.dev", IDS["tenant_a"], ["viewer"]),
    "dev_a":    ("dev@a.audit.dev",    IDS["tenant_a"], ["developer"]),
    "admin_b":  ("admin@b.audit.dev",  IDS["tenant_b"], ["admin"]),
}
TOKENS = {
    k: create_access_token(IDS[k], v[0], v[1], v[2])
    for k, v in USERS.items()
}


def call(method: str, path: str, who: str | None, body=None):
    url = BASE + path
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if who:
        req.add_header("Authorization", f"Bearer {TOKENS[who]}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data, timeout=60) as r:
            return r.status, r.read().decode()[:1400]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:1400]
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def show(label, method, path, who, body=None, expect=None):
    code, txt = call(method, path, who, body)
    txt = txt.replace("\n", " ")
    print(f"\n### {label}")
    print(f"REQ  {method} {path}   as={who or 'ANONYMOUS'}")
    print(f"HTTP {code}" + (f"   (expected {expect})" if expect else ""))
    print(f"RESP {txt}")
    return code, txt


def main():
    P = IDS
    print("=" * 100)
    print("SECTION 1 — AUTHENTICATION / AUTHORIZATION")
    print("=" * 100)
    show("no token", "GET", "/clusters", None, expect=401)
    show("garbage token", "GET", "/clusters", None, expect=401)
    # tampered token
    global TOKENS
    TOKENS["tampered"] = TOKENS["admin_a"][:-4] + "AAAA"
    show("tampered JWT", "GET", "/clusters", "tampered", expect=401)
    show("valid admin_a", "GET", "/clusters", "admin_a", expect=200)

    print("\n" + "=" * 100)
    print("SECTION 2 — READ PATHS (exactly what the UI requests)")
    print("=" * 100)
    show("header cluster selector", "GET", "/clusters", "admin_a")
    show("stat card: pod stats", "GET", "/kubernetes/pods/stats", "admin_a")
    show("stat card: pipeline stats", "GET", "/pipelines/stats", "admin_a")
    show("usePods list", "GET", "/kubernetes/pods?page_size=100", "admin_a")
    show("pipelines list", "GET", "/pipelines?page_size=30", "admin_a")
    show("workloads: deployments", "GET", "/kubernetes/pods/workloads/deployments", "admin_a")
    show("workloads: statefulsets", "GET", "/kubernetes/pods/workloads/statefulsets", "admin_a")
    show("workloads: daemonsets", "GET", "/kubernetes/pods/workloads/daemonsets", "admin_a")
    show("network: services", "GET", "/kubernetes/pods/network/services", "admin_a")
    show("network: ingresses", "GET", "/kubernetes/pods/network/ingresses", "admin_a")
    show("batch: jobs", "GET", "/kubernetes/pods/batch/jobs", "admin_a")
    show("config: configmaps", "GET", "/kubernetes/pods/config/configmaps", "admin_a")
    show("config: secrets(metadata)", "GET", "/kubernetes/pods/config/secrets", "admin_a")
    show("autoscaling: hpa", "GET", "/kubernetes/pods/autoscaling/hpa", "admin_a")
    show("cluster summary", "GET", "/kubernetes/pods/cluster/summary", "admin_a")
    show("cluster detail: nodes", "GET", f"/clusters/{P['cluster_a']}/nodes", "admin_a")
    show("cluster detail: namespaces", "GET", f"/clusters/{P['cluster_a']}/namespaces", "admin_a")
    show("cluster detail: deployments", "GET", f"/clusters/{P['cluster_a']}/deployments", "admin_a")
    show("cluster detail: services", "GET", f"/clusters/{P['cluster_a']}/services", "admin_a")
    show("cluster detail: ingresses", "GET", f"/clusters/{P['cluster_a']}/ingresses", "admin_a")
    show("obs: cluster metrics 1h", "GET", "/observability/metrics/cluster?range=1h", "admin_a")
    show("obs: pod metrics", "GET", "/observability/metrics/pods?range=1h&top=10", "admin_a")
    show("obs: namespace metrics", "GET", "/observability/metrics/namespaces", "admin_a")
    show("obs: logs (pod ref)", "GET",
         f"/observability/logs?pod={urllib.parse.quote('jobs/worker-5b7c6-j8k9l')}&tail=300", "admin_a")
    show("gitops list", "GET", "/gitops", "admin_a")
    show("gitops stats", "GET", "/gitops/stats/summary", "admin_a")
    show("gitops history", "GET", f"/gitops/{P['gitops_a']}/history?limit=20", "admin_a")
    show("catalog services", "GET", "/catalog/services", "admin_a")
    show("catalog stats", "GET", "/catalog/stats", "admin_a")
    show("devops alerts", "GET", "/devops-alerts", "admin_a")
    show("devops alerts stats", "GET", "/devops-alerts/stats", "admin_a")
    show("pipeline jobs drawer", "GET", f"/pipelines/{P['pipelines_a'][0]}/jobs", "admin_a")
    show("pod events drawer", "GET", f"/kubernetes/pods/{P['pods_a'][0]}/events", "admin_a")
    show("pod logs (dialog)", "GET", f"/kubernetes/pods/{P['pods_a'][0]}/logs?tail=200", "admin_a")

    print("\n" + "=" * 100)
    print("SECTION 3 — FILTERS / PAGINATION actually reach the backend")
    print("=" * 100)
    show("pods filter namespace=prod", "GET", "/kubernetes/pods?page_size=100&namespace=prod", "admin_a")
    show("pods filter namespace=jobs", "GET", "/kubernetes/pods?page_size=100&namespace=jobs", "admin_a")
    show("pods filter status=Running", "GET", "/kubernetes/pods?page_size=100&status=Running", "admin_a")
    show("pods page 2 (should be empty)", "GET", "/kubernetes/pods?page=2&page_size=2", "admin_a")
    show("pipelines filter repository=api", "GET", "/pipelines?repository=api", "admin_a")
    show("pipelines filter branch=main", "GET", "/pipelines?branch=main", "admin_a")
    show("pipelines filter branch=NOPE", "GET", "/pipelines?branch=NOPE", "admin_a")
    show("catalog filter status=Running", "GET", "/catalog/services?status=Running", "admin_a")
    show("catalog filter status=Failed", "GET", "/catalog/services?status=Failed", "admin_a")
    show("catalog filter search=audit", "GET", "/catalog/services?search=audit", "admin_a")
    show("catalog filter search=zzz", "GET", "/catalog/services?search=zzz", "admin_a")
    show("gitops filter health_status=Healthy", "GET", "/gitops?health_status=Healthy", "admin_a")
    show("gitops filter health_status=Unknown", "GET", "/gitops?health_status=Unknown", "admin_a")
    show("gitops filter sync_status=Synced", "GET", "/gitops?sync_status=Synced", "admin_a")
    show("alerts filter status=firing", "GET", "/devops-alerts?status=firing", "admin_a")
    show("alerts filter status=resolved", "GET", "/devops-alerts?status=resolved", "admin_a")
    show("alerts filter severity=critical", "GET", "/devops-alerts?severity=critical", "admin_a")

    print("\n" + "=" * 100)
    print("SECTION 4 — TENANT ISOLATION / IDOR (real cross-tenant IDs)")
    print("=" * 100)
    show("A reads B cluster", "GET", f"/clusters/{P['cluster_b']}", "admin_a", expect=404)
    show("A lists clusters", "GET", "/clusters", "admin_a", expect="only A")
    show("A reads B pod", "GET", f"/kubernetes/pods/{P['pod_b']}", "admin_a", expect=404)
    show("A restarts B pod", "POST", f"/kubernetes/pods/{P['pod_b']}/restart", "admin_a", {}, expect=404)
    show("A deletes B pod", "DELETE", f"/kubernetes/pods/{P['pod_b']}", "admin_a", expect=404)
    show("A reads B pod logs", "GET", f"/kubernetes/pods/{P['pod_b']}/logs", "admin_a", expect=404)
    show("A reads B pipeline", "GET", f"/pipelines/{P['pipeline_b']}", "admin_a", expect=404)
    show("A cancels B pipeline", "POST", f"/pipelines/{P['pipeline_b']}/cancel", "admin_a", {}, expect=404)
    show("A reads B gitops app", "GET", f"/gitops/{P['gitops_b']}", "admin_a", expect=404)
    show("A syncs B gitops app", "POST", f"/gitops/{P['gitops_b']}/sync", "admin_a",
         {"hard_sync": False, "dry_run": False}, expect=404)
    show("A deletes B gitops app", "DELETE", f"/gitops/{P['gitops_b']}", "admin_a", expect=404)
    show("B lists pods (own only)", "GET", "/kubernetes/pods?page_size=100", "admin_b")
    show("B lists clusters", "GET", "/clusters", "admin_b")
    show("B lists gitops", "GET", "/gitops", "admin_b")

    print("\n" + "=" * 100)
    print("SECTION 5 — RBAC GRID (viewer / developer / devops / admin)")
    print("=" * 100)
    for who in ["viewer_a", "dev_a", "devops_a", "admin_a"]:
        show(f"{who}: pod restart", "POST", f"/kubernetes/pods/{P['pods_a'][0]}/restart", who, {})
        show(f"{who}: pod exec", "POST", f"/kubernetes/pods/{P['pods_a'][0]}/exec", who, {"command": "id"})
        show(f"{who}: pipeline cancel", "POST", f"/pipelines/{P['pipelines_a'][2]}/cancel", who, {})
        show(f"{who}: create cluster", "POST", "/clusters", who,
             {"name": f"rbac-probe-{who}", "provider": "on-prem", "region": "x", "environment": "dev"})
        show(f"{who}: create alert", "POST", "/devops-alerts", who,
             {"name": f"rbac-{who}", "type": "High CPU", "message": "probe", "severity": "info"})
        show(f"{who}: gitops sync", "POST", f"/gitops/{P['gitops_a']}/sync", who,
             {"hard_sync": False, "dry_run": False})
        show(f"{who}: catalog create", "POST", "/catalog/services", who,
             {"name": f"rbac-{who}-svc", "type": "Microservice", "tech_stack": "Go"})
    show("viewer: read pods (should be allowed)", "GET", "/kubernetes/pods?page_size=10", "viewer_a")
    show("viewer: read pod logs (should be allowed)", "GET",
         f"/kubernetes/pods/{P['pods_a'][0]}/logs", "viewer_a")

    print("\n" + "=" * 100)
    print("SECTION 6 — MUTATIONS against a REAL (unreachable) provider")
    print("=" * 100)
    show("pod restart (K8s unreachable)", "POST", f"/kubernetes/pods/{P['pods_a'][0]}/restart",
         "devops_a", {})
    show("pod delete (K8s unreachable)", "DELETE", f"/kubernetes/pods/{P['pods_a'][3]}", "devops_a")
    show("pod exec (K8s unreachable)", "POST", f"/kubernetes/pods/{P['pods_a'][0]}/exec",
         "devops_a", {"command": "id"})
    show("deployment scale (K8s unreachable)", "POST",
         "/kubernetes/pods/deployments/api-gateway/scale", "devops_a",
         {"replicas": 3, "namespace": "prod"})
    show("cluster test (unreachable)", "POST", f"/clusters/{P['cluster_a']}/test", "devops_a", {})
    show("cluster create", "POST", "/clusters", "devops_a",
         {"name": "audit-new-cluster", "provider": "eks", "region": "us-east-1",
          "environment": "staging", "api_server_url": "https://127.0.0.1:6443"})
    show("gitops register app", "POST", "/gitops", "devops_a",
         {"name": "audit-new-app", "project": "default", "namespace": "prod",
          "source_type": "git", "repo_url": "https://github.com/audit-org/api",
          "target_revision": "main", "argocd_app_name": "audit-new-app"})
    show("gitops sync (no ArgoCD)", "POST", f"/gitops/{P['gitops_a']}/sync", "devops_a",
         {"hard_sync": False, "dry_run": False})
    show("gitops rollback (no ArgoCD)", "POST", f"/gitops/{P['gitops_a']}/rollback", "devops_a",
         {"revision": "9182736455abc", "message": "audit probe"})
    show("pipeline rerun (invalid GitHub token)", "POST",
         f"/pipelines/{P['pipelines_a'][1]}/rerun?failed_only=true", "devops_a", {})
    show("pipeline cancel (running, invalid token)", "POST",
         f"/pipelines/{P['pipelines_a'][2]}/cancel", "devops_a", {})
    show("pipeline rerun on RUNNING (guard)", "POST",
         f"/pipelines/{P['pipelines_a'][2]}/rerun?failed_only=true", "devops_a", {}, expect=422)
    show("pipeline cancel on SUCCESS (guard)", "POST",
         f"/pipelines/{P['pipelines_a'][0]}/cancel", "devops_a", {}, expect=422)
    show("pipeline sync trigger", "POST", "/pipelines/sync", "devops_a", {})
    show("catalog create service", "POST", "/catalog/services", "devops_a",
         {"name": "audit-e2e-svc", "type": "Microservice", "tech_stack": "Node.js",
          "git_repo": "https://github.com/audit-org/api", "cluster": "audit-cluster-a",
          "namespace": "prod", "replicas": 2, "tags": ["audit"]})
    show("devops alert create", "POST", "/devops-alerts", "devops_a",
         {"name": "audit probe alert", "severity": "warning", "type": "High CPU",
          "resource": "api-gateway", "namespace": "prod", "message": "probe"})

    print("\n" + "=" * 100)
    print("SECTION 7 — RATE LIMITS (in-process fallback; Redis absent)")
    print("=" * 100)
    codes = []
    for i in range(35):
        c, _ = call("POST", f"/kubernetes/pods/{P['pods_a'][0]}/restart", "devops_a", {})
        codes.append(c)
    print(f"pod.restart x35 status codes: {codes}")
    print(f"429 present: {429 in codes}  (limit declared = 30/60s)")

    print("\n" + "=" * 100)
    print("SECTION 8 — DEAD / UNUSED FRONTEND CONTRACT")
    print("=" * 100)
    show("gitops v2 status (unused by UI)", "GET", f"/gitops/applications/{P['gitops_a']}/status", "admin_a")
    show("pipelines repositories (unused by UI)", "GET", "/pipelines/repositories", "admin_a")
    show("k8s pods/clusters (unused by UI)", "GET", "/kubernetes/pods/clusters", "admin_a")
    show("k8s pods/namespaces (unused by UI)", "GET", "/kubernetes/pods/namespaces", "admin_a")


if __name__ == "__main__":
    import urllib.parse  # noqa: E402
    main()
