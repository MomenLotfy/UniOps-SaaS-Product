"""
DevOps Center production-audit fixture.

Builds a CLEAN SQLite database (backend/audit.db) containing exactly the
entities the DevOps Center reads/writes, for two isolated tenants, so every
endpoint can be exercised live and cross-tenant isolation can be proven with
real resource IDs.

Deliberately does NOT create a reachable Kubernetes cluster or a valid GitHub
token: the audit must prove what the product does when the provider is
unavailable, and must prove that nothing fake is fabricated in that case.

Run:  cd backend && .venv/bin/python scripts/audit_fixture.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault(
    "SECRET_KEY", "audit-fixture-secret-key-please-replace-in-production-0001")
os.environ.setdefault(
    "JWT_SECRET_KEY", "audit-fixture-jwt-secret-please-replace-in-production-1")
os.environ.setdefault("APP_ENV", "development")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession  # noqa: E402

from app.core.database import Base  # noqa: E402
import app.models  # noqa: E402,F401  (register every model)
from app.models.user import User  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.integration import Integration  # noqa: E402
from app.models.pod import Pod  # noqa: E402
from app.models.pipeline import Pipeline  # noqa: E402
from app.models.cluster import Cluster  # noqa: E402
from app.models.gitops_app import GitOpsApp  # noqa: E402
from app.models.gitops_history import GitOpsHistory  # noqa: E402
from app.models.devops_alert import DevOpsAlert  # noqa: E402
from app.models.service import CatalogService  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.utils.encryption import encrypt  # noqa: E402

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audit.db")
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"

NOW = datetime.now(timezone.utc)


def _u(email: str, role: str, tenant_id: str) -> User:
    return User(
        tenant_id=tenant_id, email=email, username=email.replace("@", "_").replace(".", "_"),
        full_name=email.split("@")[0],
        hashed_password=hash_password("AuditPassw0rd!"),
        role=role, is_active=True, is_verified=True,
    )


async def build() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    engine = create_async_engine(DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # ── Tenants ────────────────────────────────────────────────────────
        db.add_all([
            Tenant(id=TENANT_A, name="AuditCo A", slug="auditco-a", domain="a.audit.dev", plan="enterprise"),
            Tenant(id=TENANT_B, name="AuditCo B", slug="auditco-b", domain="b.audit.dev", plan="enterprise"),
        ])
        await db.flush()

        # ── Users ──────────────────────────────────────────────────────────
        admin_a  = _u("admin@a.audit.dev",  "admin",            TENANT_A)
        devops_a = _u("devops@a.audit.dev", "devops_engineer",  TENANT_A)
        viewer_a = _u("viewer@a.audit.dev", "viewer",           TENANT_A)
        dev_a    = _u("dev@a.audit.dev",    "developer",        TENANT_A)
        admin_b  = _u("admin@b.audit.dev",  "admin",            TENANT_B)
        db.add_all([admin_a, devops_a, viewer_a, dev_a, admin_b])
        await db.flush()

        # ── Integrations ───────────────────────────────────────────────────
        # Kubernetes: marked connected, but the kubeconfig points at an
        # unreachable API server.  This is the honest "provider unreachable"
        # scenario — the audit must show the real error, never fake data.
        k8s_a = Integration(
            tenant_id=TENANT_A, name="audit-k8s-a", type="kubernetes",
            status="connected", is_active=True,
            credentials={},
            config={
                "name": "audit-cluster-a",
                "kubeconfig": (
                    "apiVersion: v1\nkind: Config\nclusters:\n"
                    "- cluster:\n    server: https://127.0.0.1:6443\n"
                    "    insecure-skip-tls-verify: true\n"
                    "  name: audit\ncontexts:\n- context:\n"
                    "    cluster: audit\n    user: audit\n  name: audit\n"
                    "current-context: audit\nusers:\n- name: audit\n"
                    "  user:\n    token: audit-invalid-token\n"
                ),
            },
        )
        # GitHub: marked connected with a syntactically valid but invalid PAT.
        gh_a = Integration(
            tenant_id=TENANT_A, name="audit-github-a", type="github",
            status="connected", is_active=True,
            credentials={"token": encrypt("ghp_auditinvalidtoken000000000000000000")},
            config={"owner": "audit-org"},
        )
        # ArgoCD: NOT created — GitOps sync/rollback must report NOT_CONFIGURED.
        k8s_b = Integration(
            tenant_id=TENANT_B, name="audit-k8s-b", type="kubernetes",
            status="connected", is_active=True,
            credentials={}, config={"name": "audit-cluster-b"},
        )
        db.add_all([k8s_a, gh_a, k8s_b])
        await db.flush()

        # ── Clusters ───────────────────────────────────────────────────────
        cluster_a = Cluster(
            tenant_id=TENANT_A, name="audit-cluster-a", provider="on-prem",
            region="local", environment="production",
            api_server_url="https://127.0.0.1:6443",
            status="pending", node_count=0, pod_count=0,
            cpu_usage_pct=0.0, memory_usage_pct=0.0,
        )
        cluster_b = Cluster(
            tenant_id=TENANT_B, name="audit-cluster-b", provider="eks",
            region="us-east-1", environment="staging", status="pending",
        )
        db.add_all([cluster_a, cluster_b])
        await db.flush()

        # ── Pods (tenant A) ────────────────────────────────────────────────
        pod_specs = [
            ("api-gateway-7d9f8-x2k4p", "prod",   "Running",  2, 0.25, 0.5,  0.12,  256 * 1024**2, 512 * 1024**2, 190 * 1024**2),
            ("payments-6c8d9-m1n2q",    "prod",   "Running",  0, 0.5,  1.0,  0.42,  512 * 1024**2, 1024 * 1024**2, 610 * 1024**2),
            ("worker-5b7c6-j8k9l",      "jobs",   "CrashLoopBackOff", 9, 0.1, 0.2, 0.09, 128 * 1024**2, 256 * 1024**2, 250 * 1024**2),
            ("frontend-4a6b5-p3q4r",    "prod",   "Pending",  0, 0.2,  0.4,  None, None, None, None),
        ]
        pods = []
        for i, (name, ns, status, restarts, creq, clim, cuse, mreq, mlim, muse) in enumerate(pod_specs):
            pods.append(Pod(
                tenant_id=TENANT_A, integration_id=k8s_a.id,
                name=name, namespace=ns, cluster="audit-cluster-a",
                status=status, phase=status, node=f"node-{i % 2}",
                cpu_request=creq, cpu_limit=clim, cpu_usage=cuse,
                memory_request=mreq, memory_limit=mlim, memory_usage=muse,
                restart_count=restarts,
                containers=[{"name": "app", "image": "nginx:1.27", "ready": status == "Running",
                             "restartCount": restarts}],
                labels={"app": name.split("-")[0]},
                created_at=NOW - timedelta(hours=5),
            ))
        # One pod in tenant B — used for cross-tenant IDOR probes.
        pod_b = Pod(
            tenant_id=TENANT_B, integration_id=k8s_b.id,
            name="tenant-b-secret-pod", namespace="prod", cluster="audit-cluster-b",
            status="Running", phase="Running", restart_count=0,
            created_at=NOW - timedelta(hours=5),
        )
        db.add_all(pods + [pod_b])
        await db.flush()

        # ── Pipelines (tenant A) ───────────────────────────────────────────
        pipe_specs = [
            ("CI", "audit-org/api", "main", "success",  142, "9182736455"),
            ("CI", "audit-org/api", "feat/x", "failed",  88, "9182736456"),
            ("Deploy", "audit-org/api", "main", "running", None, "9182736457"),
        ]
        pipes = []
        for name, repo, branch, status, dur, ext in pipe_specs:
            pipes.append(Pipeline(
                tenant_id=TENANT_A, integration_id=gh_a.id, external_id=ext,
                name=name, repository=repo, branch=branch, status=status,
                duration=dur, commit_sha=ext + "abc",
                commit_message=f"audit fixture commit for {name}",
                started_at=NOW - timedelta(hours=2),
                logs_url=f"https://github.com/{repo}/actions/runs/{ext}",
                metadata_={"run_id": ext},
            ))
        pipe_b = Pipeline(
            tenant_id=TENANT_B, integration_id=None, external_id="b-run-1",
            name="CI", repository="audit-org-b/api", branch="main", status="failed",
        )
        db.add_all(pipes + [pipe_b])
        await db.flush()

        # ── GitOps apps (tenant A) ─────────────────────────────────────────
        app_a = GitOpsApp(
            tenant_id=TENANT_A, cluster_id=cluster_a.id, name="audit-app-a",
            project="default", namespace="prod", source_type="helm",
            repo_url="https://github.com/audit-org/api", target_revision="main",
            helm_chart="api", health_status="Unknown", sync_status="Unknown",
            argocd_app_name="audit-app-a",
        )
        app_b = GitOpsApp(
            tenant_id=TENANT_B, name="audit-app-b", namespace="prod",
            health_status="Healthy", sync_status="Synced",
        )
        db.add_all([app_a, app_b])
        await db.flush()
        db.add(GitOpsHistory(
            tenant_id=TENANT_A, app_id=app_a.id, revision="9182736455abc",
            short_sha="9182736", author="audit", message="initial deploy",
            deployed_at=NOW - timedelta(hours=3), deployed_by="admin@a.audit.dev",
            status="Succeeded", source_type="helm",
        ))

        # ── DevOps alerts (tenant A) ───────────────────────────────────────
        db.add(DevOpsAlert(
            tenant_id=TENANT_A, cluster_id=cluster_a.id, namespace="jobs",
            name="worker CrashLoopBackOff", severity="critical",
            type="CrashLoopBackOff", resource="worker-5b7c6-j8k9l",
            message="Pod restarting 9 times in the last 10 minutes",
            status="firing", fired_at=NOW - timedelta(minutes=12),
        ))

        # ── Catalog services (tenant A) ────────────────────────────────────
        db.add(CatalogService(
            tenant_id=TENANT_A, name="audit-svc-a", type="Microservice",
            tech_stack="Node.js", status="Running", cluster="audit-cluster-a",
            namespace="prod", replicas=2, tags=["audit"],
        ))

        await db.commit()

        ids = {
            "tenant_a": TENANT_A, "tenant_b": TENANT_B,
            "admin_a": admin_a.id, "devops_a": devops_a.id,
            "viewer_a": viewer_a.id, "dev_a": dev_a.id, "admin_b": admin_b.id,
            "k8s_a": k8s_a.id, "gh_a": gh_a.id,
            "cluster_a": cluster_a.id, "cluster_b": cluster_b.id,
            "pods_a": [p.id for p in pods], "pod_b": pod_b.id,
            "pipelines_a": [p.id for p in pipes], "pipeline_b": pipe_b.id,
            "gitops_a": app_a.id, "gitops_b": app_b.id,
        }
    await engine.dispose()
    print(json.dumps(ids, indent=2))
    with open(os.path.join(os.path.dirname(DB_PATH), ".audit_ids.json"), "w") as fh:
        json.dump(ids, fh, indent=2)


if __name__ == "__main__":
    asyncio.run(build())
