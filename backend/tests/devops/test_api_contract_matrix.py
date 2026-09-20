"""
Mandatory test class B — API contract for every visible DevOps Center path.

The route table is derived from the live ASGI app rather than hardcoded, so this
suite cannot silently drift when a new DevOps endpoint is added: a new route is
picked up automatically and must satisfy the same contract.

Dimensions covered here:
  * authn          — every route rejects missing and forged credentials
  * tenant isolation — a resource id owned by tenant B is not reachable from A
  * not-found      — unknown ids 404 rather than 200-with-empty

Success and provider-failure behaviour for these paths lives in
``test_resource_endpoints.py``, ``test_provider_contract.py`` and
``test_catalog_filters.py``.
"""
from __future__ import annotations

import jwt as pyjwt
import pytest

from app.main import app


DEVOPS_PREFIXES = (
    "/api/v1/kubernetes/pods",
    "/api/v1/gitops",
    "/api/v1/clusters",
    "/api/v1/pipelines",
    "/api/v1/catalog",
    "/api/v1/devops-alerts",
    "/api/v1/observability",
)

# Bodies that satisfy schema validation for the mutation routes, so a 401 proves
# the *auth* gate fired rather than a request-validation error.
_BODIES = {
    ("post", "/api/v1/gitops"): {
        "name": "t", "repo_url": "https://github.com/a/b", "path": ".",
        "cluster": "c", "namespace": "default",
    },
    ("post", "/api/v1/devops-alerts"): {
        "type": "High CPU", "message": "m", "severity": "warning",
    },
    ("post", "/api/v1/kubernetes/pods/deployments/{deployment_name}/scale"): {"replicas": 2},
}


def _devops_routes() -> list[tuple[str, str]]:
    """Every method+path the app exposes under a DevOps Center prefix."""
    out = []
    for r in app.routes:
        p = getattr(r, "path", "")
        if any(p.startswith(x) for x in DEVOPS_PREFIXES):
            for m in sorted(getattr(r, "methods", set()) - {"HEAD", "OPTIONS"}):
                out.append((m.lower(), p))
    return sorted(set(out), key=lambda x: (x[1], x[0]))


ROUTES = _devops_routes()


def _concrete(method: str, path: str) -> tuple[str, dict | None]:
    """Substitute path params and pick a body if one is required."""
    p = (path.replace("{pod_id}", "no-such-pod")
             .replace("{app_id}", "no-such-app")
             .replace("{pipeline_id}", "no-such-pipeline")
             .replace("{cluster_id}", "no-such-cluster")
             .replace("{service_id}", "no-such-service")
             .replace("{alert_id}", "no-such-alert")
             .replace("{deployment_name}", "no-such-deploy"))
    body = _BODIES.get((method, path))
    if body is None and method in ("post", "patch", "put"):
        body = {}
    return p, body


async def _call(client, method: str, path: str, headers=None, body=None):
    kwargs = {"headers": headers} if headers else {}
    if body is not None:
        kwargs["json"] = body
    return await getattr(client, method)(path, **kwargs)


# ── authn ─────────────────────────────────────────────────────────────────────

def test_route_table_is_discovered_not_hardcoded():
    """Guard: the sweep must actually see the DevOps surface."""
    assert len(ROUTES) >= 60, f"only {len(ROUTES)} DevOps routes discovered"
    joined = "\n".join(p for _, p in ROUTES)
    for marker in ("/kubernetes/pods", "/gitops", "/clusters", "/pipelines",
                   "/catalog", "/observability"):
        assert marker in joined


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", ROUTES, ids=[f"{m} {p}" for m, p in ROUTES])
async def test_every_devops_route_rejects_anonymous_callers(client, method, path):
    """No DevOps Center route may be publicly reachable."""
    concrete, body = _concrete(method, path)
    r = await _call(client, method, concrete, body=body)
    assert r.status_code in (401, 403), (
        f"{method.upper()} {path} returned {r.status_code} without credentials"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", ROUTES, ids=[f"{m} {p}" for m, p in ROUTES])
async def test_every_devops_route_rejects_forged_tokens(client, method, path):
    """
    A well-formed but unsigned-by-us JWT must not authenticate. This is the
    case a broken secret configuration would silently allow.
    """
    from datetime import datetime, timedelta, timezone

    from app.config import settings

    wrong_secret = "this-is-not-the-server-secret-key-0000000000"
    assert wrong_secret != settings.JWT_SECRET_KEY
    now = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {
            "sub": "attacker", "email": "a@b.c", "tenant_id": "forged-tenant",
            "roles": ["admin"], "exp": now + timedelta(minutes=30), "iat": now,
            "type": "access",
        },
        wrong_secret, algorithm=settings.JWT_ALGORITHM,
    )
    concrete, body = _concrete(method, path)
    r = await _call(client, method, concrete,
                    headers={"Authorization": f"Bearer {token}"}, body=body)
    assert r.status_code in (401, 403), (
        f"{method.upper()} {path} accepted a forged token ({r.status_code})"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", ROUTES, ids=[f"{m} {p}" for m, p in ROUTES])
async def test_every_devops_route_rejects_malformed_authorization(client, method, path):
    """Garbage in the Authorization header must not 500."""
    concrete, body = _concrete(method, path)
    r = await _call(client, method, concrete,
                    headers={"Authorization": "Bearer not.a.jwt"}, body=body)
    assert r.status_code in (401, 403), (
        f"{method.upper()} {path} returned {r.status_code} for a malformed token"
    )


# ── tenant isolation ──────────────────────────────────────────────────────────

async def _register(client, email: str, org: str):
    username = email.split("@")[0].replace("-", "_")
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "full_name": "Admin",
        "password": "Str0ng!Pass9", "company_name": org,
    })
    assert r.status_code in (200, 201), r.text
    tok = r.json()["data"]["access_token"]
    claims = pyjwt.decode(tok, options={"verify_signature": False})
    return {"Authorization": f"Bearer {tok}"}, claims["tenant_id"]


@pytest.fixture
async def two_tenants(client):
    hA, tidA = await _register(client, "ct-a@test.dev", "OrgContractA")
    hB, tidB = await _register(client, "ct-b@test.dev", "OrgContractB")
    return client, hA, tidA, hB, tidB


@pytest.mark.asyncio
async def test_gitops_row_of_tenant_b_is_invisible_to_a(two_tenants, db_session):
    from app.models.gitops_app import GitOpsApp

    client, hA, tidA, hB, tidB = two_tenants
    app_row = GitOpsApp(
        tenant_id=tidB, name="b-only-app", repo_url="https://github.com/b/x",
        path=".", namespace="default", cluster_server="https://b.example:6443",
    )
    db_session.add(app_row)
    await db_session.commit()

    # A cannot read it
    r = await client.get(f"/api/v1/gitops/{app_row.id}", headers=hA)
    assert r.status_code == 404

    # A cannot delete it — and must be told it does not exist (BUG-008)
    r = await client.delete(f"/api/v1/gitops/{app_row.id}", headers=hA)
    assert r.status_code == 404

    # The row is untouched
    still = await db_session.get(GitOpsApp, app_row.id)
    assert still is not None
    assert still.tenant_id == tidB

    # B can still see its own row
    r = await client.get(f"/api/v1/gitops/{app_row.id}", headers=hB)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cluster_of_tenant_b_is_invisible_to_a(two_tenants, db_session):
    from app.models.cluster import Cluster

    client, hA, tidA, hB, tidB = two_tenants
    row = Cluster(tenant_id=tidB, name="b-cluster", provider="self-hosted",
                    kubeconfig_encrypted="x")
    db_session.add(row)
    await db_session.commit()

    for method, path in (
        ("get",    f"/api/v1/clusters/{row.id}"),
        ("post",   f"/api/v1/clusters/{row.id}/test"),
        ("delete", f"/api/v1/clusters/{row.id}"),
    ):
        r = await _call(client, method, path, headers=hA,
                        body={} if method == "post" else None)
        assert r.status_code == 404, f"{method} {path} -> {r.status_code}"

    still = await db_session.get(Cluster, row.id)
    assert still is not None


@pytest.mark.asyncio
async def test_catalog_list_never_includes_another_tenants_services(two_tenants, db_session):
    from app.models.service import CatalogService

    client, hA, tidA, hB, tidB = two_tenants
    for tid, name in ((tidA, "a-svc"), (tidB, "b-svc")):
        db_session.add(CatalogService(
            tenant_id=tid, name=name, type="Microservice",
            tech_stack="Other", status="Running",
        ))
    await db_session.commit()

    r = await client.get("/api/v1/catalog/services", headers=hA)
    assert r.status_code == 200
    names = {s["name"] for s in r.json()["data"]}
    assert names == {"a-svc"}
    assert r.json()["total"] == 1


@pytest.mark.asyncio
async def test_pod_of_tenant_b_is_invisible_to_a(two_tenants, db_session):
    from app.models.pod import Pod

    client, hA, tidA, hB, tidB = two_tenants
    pod = Pod(tenant_id=tidB, name="b-pod", namespace="default",
              cluster="b-cluster", status="Running")
    db_session.add(pod)
    await db_session.commit()

    for path in (f"/api/v1/kubernetes/pods/{pod.id}",
                 f"/api/v1/kubernetes/pods/{pod.id}/logs",
                 f"/api/v1/kubernetes/pods/{pod.id}/events"):
        r = await client.get(path, headers=hA)
        assert r.status_code == 404, f"{path} -> {r.status_code}"

    still = await db_session.get(Pod, pod.id)
    assert still is not None


# ── not-found ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/api/v1/kubernetes/pods/definitely-not-real",
    "/api/v1/kubernetes/pods/definitely-not-real/logs",
    "/api/v1/kubernetes/pods/definitely-not-real/events",
    "/api/v1/gitops/definitely-not-real",
    "/api/v1/clusters/definitely-not-real",
    "/api/v1/catalog/services/definitely-not-real",
    "/api/v1/pipelines/definitely-not-real",
])
async def test_unknown_ids_return_404_not_empty_success(client, path):
    headers, _ = await _register(client, "nf@test.dev", "OrgNotFound")
    r = await client.get(path, headers=headers)
    assert r.status_code == 404, f"{path} -> {r.status_code}"
    # A 404 must not be disguised as a successful empty payload
    body = r.json()
    assert body.get("success") is not True


@pytest.mark.asyncio
async def test_mutations_on_unknown_ids_are_404(client):
    headers, _ = await _register(client, "nfm@test.dev", "OrgNotFoundMut")
    cases = [
        ("post",   "/api/v1/kubernetes/pods/definitely-not-real/restart", None),
        ("delete", "/api/v1/kubernetes/pods/definitely-not-real", None),
        ("delete", "/api/v1/gitops/definitely-not-real", None),
        ("delete", "/api/v1/catalog/services/definitely-not-real", None),
    ]
    for method, path, body in cases:
        r = await _call(client, method, path, headers=headers, body=body)
        assert r.status_code == 404, f"{method.upper()} {path} -> {r.status_code}"
