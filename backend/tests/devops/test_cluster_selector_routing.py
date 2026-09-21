"""BUG-010 end-to-end cluster routing + ArgoCD TLS verification.

Two hardening items, both proven through the real code paths.

**1. The cluster selector must route, not just relabel.**

Before this pass ``selectedClusterId`` was read only to render the dropdown's
own label and highlight; it reached no request. The nine Control-Plane resource
endpoints already accepted ``cluster_id``, and this pass adds it to
``GET /kubernetes/pods`` and ``GET /kubernetes/pods/stats`` — the two remaining
cluster-shaped reads in the DevOps Center.

The required behaviour mirrors the mandatory cluster-routing class:

    cluster = A              -> only A's pods
    cluster = B              -> only B's pods
    A then B                 -> the result actually changes
    cluster = random UUID    -> 404, never another cluster's data
    cluster = other tenant's -> 404, and the caller learns nothing about it
    cluster omitted          -> tenant-wide, exactly as before

**2. ArgoCD must verify TLS by default.**

Five helpers in ``gitops.py`` hardcoded ``httpx.AsyncClient(verify=False)``,
ignoring the ``insecure`` flag that ``_get_argocd_creds`` already resolves and
hands them. They now honour it, matching the two real ArgoCD clients
(``integrations/gitops/argocd_client.py`` and
``core/deployment_engine/argocd.py``), which already used
``verify=not self.insecure``.
"""
from __future__ import annotations

import io
import tokenize

import pytest
import pytest_asyncio

from app.api.v1.endpoints import gitops as gitops_ep
from app.core.security import create_access_token
from app.models.cluster import Cluster
from app.models.integration import Integration
from app.models.pod import Pod
from app.models.tenant import Tenant


TENANT_A = "t-csel-a"
TENANT_B = "t-csel-b"


def _hdr(tenant: str, roles: list[str], uid: str = "u") -> dict:
    return {"Authorization": "Bearer " + create_access_token(
        user_id=uid, email=f"{uid}@csel.dev", tenant_id=tenant, roles=roles,
    )}


def _admin(tenant: str = TENANT_A) -> dict:
    return _hdr(tenant, ["admin"], "admin-csel")


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def two_clusters_with_pods(client, db_session):
    """
    Tenant A owns clusters A and B, each with two pods. Tenant B owns a cluster
    whose name is deliberately similar, to prove scoping is by resolved cluster
    and not by string luck.
    """
    for tid, slug in ((TENANT_A, "csel-a"), (TENANT_B, "csel-b")):
        db_session.add(Tenant(name=f"Sel {slug}", slug=slug))
    await db_session.flush()

    cA = Cluster(tenant_id=TENANT_A, name="cluster-a", provider="on-prem",
                 region="local", environment="production")
    cB = Cluster(tenant_id=TENANT_A, name="cluster-b", provider="on-prem",
                 region="local", environment="staging")
    cOther = Cluster(tenant_id=TENANT_B, name="cluster-other", provider="eks",
                     region="us-east-1", environment="production")
    db_session.add_all([cA, cB, cOther])
    await db_session.flush()

    pods = [
        Pod(tenant_id=TENANT_A, name="a-1", namespace="default",
            cluster="cluster-a", status="Running", restart_count=0),
        Pod(tenant_id=TENANT_A, name="a-2", namespace="default",
            cluster="cluster-a", status="Running", restart_count=9),
        Pod(tenant_id=TENANT_A, name="b-1", namespace="default",
            cluster="cluster-b", status="Failed", restart_count=1),
        Pod(tenant_id=TENANT_A, name="b-2", namespace="default",
            cluster="cluster-b", status="Pending", restart_count=0),
        # A pod belonging to tenant B. It must never appear in tenant A's
        # results, with or without a cluster filter.
        Pod(tenant_id=TENANT_B, name="other-1", namespace="default",
            cluster="cluster-other", status="Running", restart_count=0),
    ]
    db_session.add_all(pods)
    await db_session.commit()

    return {"cA": cA.id, "cB": cB.id, "cOther": cOther.id}


def _names(payload) -> set[str]:
    """Pod names out of an APIResponse[PaginatedResponse] envelope."""
    body = payload.get("data") if isinstance(payload, dict) else payload
    rows = body.get("data") if isinstance(body, dict) else body
    return {r["name"] for r in (rows or [])}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Selecting cluster A returns A; selecting B returns B
# ─────────────────────────────────────────────────────────────────────────────

async def test_selecting_cluster_a_returns_only_cluster_a(client, two_clusters_with_pods):
    r = await client.get(
        f"/api/v1/kubernetes/pods?cluster_id={two_clusters_with_pods['cA']}",
        headers=_admin(),
    )
    assert r.status_code == 200
    assert _names(r.json()) == {"a-1", "a-2"}


async def test_selecting_cluster_b_returns_only_cluster_b(client, two_clusters_with_pods):
    r = await client.get(
        f"/api/v1/kubernetes/pods?cluster_id={two_clusters_with_pods['cB']}",
        headers=_admin(),
    )
    assert r.status_code == 200
    assert _names(r.json()) == {"b-1", "b-2"}


async def test_switching_a_then_b_changes_the_result(client, two_clusters_with_pods):
    """The selector must drive the request, not be read once and ignored."""
    a = (await client.get(
        f"/api/v1/kubernetes/pods?cluster_id={two_clusters_with_pods['cA']}",
        headers=_admin(),
    )).json()
    b = (await client.get(
        f"/api/v1/kubernetes/pods?cluster_id={two_clusters_with_pods['cB']}",
        headers=_admin(),
    )).json()
    assert _names(a) == {"a-1", "a-2"}
    assert _names(b) == {"b-1", "b-2"}
    assert _names(a) != _names(b)
    assert not (_names(a) & _names(b)), "the two selections must not overlap"


async def test_stats_follow_the_selected_cluster(client, two_clusters_with_pods):
    """The summary tiles must describe the selected cluster, not the tenant."""
    a = await client.get(
        f"/api/v1/kubernetes/pods/stats?cluster_id={two_clusters_with_pods['cA']}",
        headers=_admin(),
    )
    b = await client.get(
        f"/api/v1/kubernetes/pods/stats?cluster_id={two_clusters_with_pods['cB']}",
        headers=_admin(),
    )
    assert a.status_code == 200 and b.status_code == 200
    a_stats, b_stats = a.json()["data"], b.json()["data"]
    assert a_stats["total"] == 2 and a_stats["running"] == 2
    assert b_stats["total"] == 2 and b_stats["running"] == 0
    assert b_stats["failed"] == 1 and b_stats["pending"] == 1
    # cluster-a holds the only pod with restart_count > 5
    assert a_stats["high_restart_count"] == 1
    assert b_stats["high_restart_count"] == 0


async def test_omitting_the_selector_keeps_tenant_wide_behaviour(client, two_clusters_with_pods):
    """No selection = 'All Clusters'. The parameter is absent, not blank."""
    r = await client.get("/api/v1/kubernetes/pods?page_size=100", headers=_admin())
    assert r.status_code == 200
    assert _names(r.json()) == {"a-1", "a-2", "b-1", "b-2"}

    s = await client.get("/api/v1/kubernetes/pods/stats", headers=_admin())
    assert s.json()["data"]["total"] == 4


# ─────────────────────────────────────────────────────────────────────────────
# 2. Wrong / nonexistent / foreign clusters are rejected
# ─────────────────────────────────────────────────────────────────────────────

async def test_nonexistent_cluster_id_is_rejected(client, two_clusters_with_pods):
    r = await client.get(
        "/api/v1/kubernetes/pods?cluster_id=11111111-1111-1111-1111-111111111111",
        headers=_admin(),
    )
    assert r.status_code == 404, r.text
    # A rejection must not quietly degrade into tenant-wide data.
    assert "a-1" not in r.text


async def test_other_tenants_cluster_id_is_rejected(client, two_clusters_with_pods):
    """A foreign cluster id is a 404, not a 403 and not its data."""
    r = await client.get(
        f"/api/v1/kubernetes/pods?cluster_id={two_clusters_with_pods['cOther']}",
        headers=_admin(),
    )
    assert r.status_code == 404, r.text
    assert "other-1" not in r.text


async def test_stats_reject_a_foreign_cluster_id(client, two_clusters_with_pods):
    r = await client.get(
        f"/api/v1/kubernetes/pods/stats?cluster_id={two_clusters_with_pods['cOther']}",
        headers=_admin(),
    )
    assert r.status_code == 404, r.text


async def test_cluster_scoping_never_leaks_another_tenants_pods(client, two_clusters_with_pods):
    """Tenant B asking for its own cluster sees its own pod and nothing else."""
    r = await client.get(
        f"/api/v1/kubernetes/pods?cluster_id={two_clusters_with_pods['cOther']}",
        headers=_admin(TENANT_B),
    )
    assert r.status_code == 200
    assert _names(r.json()) == {"other-1"}


async def test_cluster_filter_composes_with_the_existing_name_filter(
    client, two_clusters_with_pods
):
    """The pre-existing `cluster` (name) parameter keeps working alongside."""
    r = await client.get("/api/v1/kubernetes/pods?cluster=cluster-b", headers=_admin())
    assert r.status_code == 200
    assert _names(r.json()) == {"b-1", "b-2"}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Pod.cluster can be the integration's name — both labels resolve
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cluster_pod_scope_includes_the_matching_integration_name(db_session):
    """
    ``sync_pods`` writes ``pod.cluster = data.get("cluster") or
    integration.name``, and there is no FK between ``clusters`` and
    ``integrations``. A cluster whose pods were labelled with the integration's
    name must still resolve — via the same name-matching convention
    ``get_client_for_cluster`` already uses.
    """
    from app.services.kubernetes_service import KubernetesService

    tenant = Tenant(name="Scope Tenant", slug="scope-tenant")
    db_session.add(tenant)
    await db_session.flush()

    integ = Integration(
        tenant_id=tenant.id, name="prod-integration", type="kubernetes",
        status="connected", is_active=True, credentials={},
        config={"name": "prod-cluster"},
    )
    cluster = Cluster(tenant_id=tenant.id, name="prod-cluster", provider="eks",
                      region="us-east-1", environment="production")
    db_session.add_all([integ, cluster])
    await db_session.commit()

    svc = KubernetesService(db_session)
    scope = await svc.cluster_pod_scope(tenant.id, cluster.id)
    assert scope == {"prod-cluster", "prod-integration"}


@pytest.mark.asyncio
async def test_cluster_pod_scope_rejects_a_foreign_cluster(db_session):
    """The resolver itself must 404 rather than return some other cluster."""
    from app.core.exceptions import NotFoundError
    from app.services.kubernetes_service import KubernetesService

    owner = Tenant(name="Owner", slug="scope-owner")
    intruder = Tenant(name="Intruder", slug="scope-intruder")
    db_session.add_all([owner, intruder])
    await db_session.flush()
    cluster = Cluster(tenant_id=owner.id, name="owner-cluster", provider="eks",
                      region="r", environment="production")
    db_session.add(cluster)
    await db_session.commit()

    svc = KubernetesService(db_session)
    with pytest.raises(NotFoundError):
        await svc.cluster_pod_scope(intruder.id, cluster.id)


# ─────────────────────────────────────────────────────────────────────────────
# 4. ArgoCD TLS: verification ON by default, OFF only on explicit opt-out
# ─────────────────────────────────────────────────────────────────────────────

HELPERS = [
    ("_argocd_list_apps",   ("creds",)),
    ("_argocd_sync",        ("creds", "app")),
    ("_argocd_rollback",    ("creds", "app", "rev")),
    ("_argocd_get_history", ("creds", "app")),
    ("_argocd_get_revision", ("creds", "app")),
]


class _CaptureClient:
    """Stand-in for httpx.AsyncClient that records the `verify` kwarg."""

    captured: list = []

    def __init__(self, *args, **kwargs):
        _CaptureClient.captured.append(kwargs.get("verify", "MISSING"))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, *a, **k):
        raise RuntimeError("transport stub — not a real response")

    async def post(self, *a, **k):
        raise RuntimeError("transport stub — not a real response")


async def _call_helper(name: str, creds: dict) -> None:
    """Invoke one `_argocd_*` helper with the arguments its signature needs."""
    fn = getattr(gitops_ep, name)
    if name == "_argocd_list_apps":
        await fn(creds)
    elif name == "_argocd_sync":
        await fn(creds, "demo-app")
    elif name == "_argocd_rollback":
        await fn(creds, "demo-app", "abc1234")
    elif name in ("_argocd_get_history", "_argocd_get_revision"):
        await fn(creds, "demo-app")
    else:  # pragma: no cover - guards against a renamed helper
        raise AssertionError(f"unhandled helper {name}")


@pytest.mark.parametrize("helper", [h for h, _ in HELPERS])
@pytest.mark.asyncio
async def test_argocd_helper_verifies_tls_by_default(monkeypatch, helper):
    """`insecure` absent -> TLS verification ON."""
    _CaptureClient.captured = []
    monkeypatch.setattr(gitops_ep.httpx, "AsyncClient", _CaptureClient)

    creds = {"server": "https://argocd.example", "token": "t"}
    if helper == "_argocd_rollback":
        # rollback resolves history first, which also goes through AsyncClient
        # rollback resolves a SHA through history before it calls the API;
        # return a matching entry so it reaches the client construction.
        monkeypatch.setattr(
            gitops_ep, "_argocd_get_history",
            lambda *a, **k: _async_value([{"id": 7, "revision": "abc1234def"}]),
        )
    await _call_helper(helper, creds)

    assert _CaptureClient.captured, f"{helper} never built an httpx client"
    assert all(v is True for v in _CaptureClient.captured), (
        f"{helper} built a client with verify={_CaptureClient.captured}"
    )


@pytest.mark.parametrize("helper", [h for h, _ in HELPERS])
@pytest.mark.asyncio
async def test_argocd_helper_skips_tls_only_on_explicit_opt_out(monkeypatch, helper):
    """`insecure: true` -> TLS verification OFF, i.e. the flag is really read."""
    _CaptureClient.captured = []
    monkeypatch.setattr(gitops_ep.httpx, "AsyncClient", _CaptureClient)

    creds = {"server": "https://argocd.example", "token": "t", "insecure": True}
    if helper == "_argocd_rollback":
        # rollback resolves a SHA through history before it calls the API;
        # return a matching entry so it reaches the client construction.
        monkeypatch.setattr(
            gitops_ep, "_argocd_get_history",
            lambda *a, **k: _async_value([{"id": 7, "revision": "abc1234def"}]),
        )
    await _call_helper(helper, creds)

    assert _CaptureClient.captured, f"{helper} never built an httpx client"
    assert all(v is False for v in _CaptureClient.captured), (
        f"{helper} ignored the insecure flag: verify={_CaptureClient.captured}"
    )


async def _async_value(value):
    return value


def test_no_hardcoded_verify_false_remains_in_gitops_endpoints():
    """
    Source-level guard. Tokenises first, because the module's own explanatory
    comments contain the literal string `verify=False` and would inflate a naive
    grep — the same trap that hid a regression earlier in this work.
    """
    import pathlib

    src = pathlib.Path(gitops_ep.__file__).read_text()
    comment_lines = {
        t.start[0]
        for t in tokenize.generate_tokens(io.StringIO(src).readline)
        if t.type == tokenize.COMMENT
    }
    offenders = [
        i for i, line in enumerate(src.splitlines(), 1)
        if "verify=False" in line and i not in comment_lines
    ]
    assert offenders == [], (
        f"gitops.py still hardcodes verify=False at line(s) {offenders}"
    )
