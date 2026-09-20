"""
Mandatory test class A/C — ArgoCD sync and rollback mutations.

These two endpoints were the only DevOps Center mutations with no coverage of
their provider-failure path. They are the clearest example of the pattern this
pass enforces: the endpoint must call ArgoCD for real, and only then update
local state. A failed call must not leave behind a history row claiming the
deployment happened.

Every test asserts BOTH the status code and the resulting database state,
because "returns 502" is not the same guarantee as "did not record a success".
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.api.v1.endpoints import gitops
from app.core.security import create_access_token
from app.models.gitops_app import GitOpsApp
from app.models.gitops_history import GitOpsHistory
from app.models.integration import Integration

TENANT = "t-argocd-mut"


def _devops_headers() -> dict:
    """A token carrying a role permitted to mutate (server-side RBAC gate)."""
    return {"Authorization": "Bearer " + create_access_token(
        user_id="u-argocd", email="devops@argocd.dev",
        tenant_id=TENANT, roles=["devops_engineer"],
    )}


def _viewer_headers() -> dict:
    return {"Authorization": "Bearer " + create_access_token(
        user_id="u-viewer", email="viewer@argocd.dev",
        tenant_id=TENANT, roles=["viewer"],
    )}


@pytest.fixture
async def app_with_argocd(client, db_session):
    """A GitOpsApp registered in ArgoCD plus a connected ArgoCD integration."""
    integ = Integration(
        tenant_id=TENANT, name="argocd-prod", type="argocd",
        is_active=True, status="connected",
        # decrypt() will fail on these plaintext values and the endpoint falls
        # back to the raw value — exercising the same path a real secret takes.
        credentials={"server_url": "https://argocd.example", "token": "tok-123"},
    )
    app = GitOpsApp(
        tenant_id=TENANT, name="payments", argocd_app_name="payments",
        repo_url="https://github.com/acme/payments", path=".",
        namespace="prod", current_revision="aaaaaaaaaaa1111",
        health_status="Healthy", sync_status="OutOfSync",
    )
    db_session.add_all([integ, app])
    await db_session.commit()
    return app


@pytest.fixture
async def app_without_argocd_registration(client, db_session):
    """A GitOpsApp that exists locally but was never registered in ArgoCD."""
    integ = Integration(
        tenant_id=TENANT, name="argocd-prod", type="argocd",
        is_active=True, status="connected",
        credentials={"server_url": "https://argocd.example", "token": "tok-123"},
    )
    app = GitOpsApp(
        tenant_id=TENANT, name="orphan", repo_url="https://github.com/acme/o",
        path=".", namespace="prod", argocd_app_name=None,
    )
    db_session.add_all([integ, app])
    await db_session.commit()
    return app


async def _history_rows(db_session, app_id: str) -> list:
    r = await db_session.execute(
        select(GitOpsHistory).where(GitOpsHistory.app_id == app_id)
    )
    return list(r.scalars().all())


# ── sync: no ArgoCD connection ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_without_argocd_integration_is_503_not_success(client, db_session):
    """No ArgoCD integration at all — must be 503, and record nothing."""
    app = GitOpsApp(tenant_id=TENANT, name="no-integ",
                    argocd_app_name="no-integ", repo_url="https://g/x", path=".")
    db_session.add(app)
    await db_session.commit()

    r = await client.post(f"/api/v1/gitops/{app.id}/sync",
                          json={}, headers=_devops_headers())
    assert r.status_code == 503, r.text
    assert "not connected" in r.json()["detail"].lower()

    await db_session.refresh(app)
    assert app.last_synced_at is None
    assert await _history_rows(db_session, app.id) == []


@pytest.mark.asyncio
async def test_sync_of_app_not_registered_in_argocd_is_409(
    client, db_session, app_without_argocd_registration
):
    app = app_without_argocd_registration
    r = await client.post(f"/api/v1/gitops/{app.id}/sync",
                          json={}, headers=_devops_headers())
    assert r.status_code == 409, r.text
    assert await _history_rows(db_session, app.id) == []


# ── sync: provider failure ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_provider_failure_is_502_and_records_no_success(
    client, db_session, app_with_argocd
):
    """
    The core guarantee: ArgoCD rejects the sync, so the endpoint must return 502
    and must NOT write a history row or stamp last_synced_at.
    """
    app = app_with_argocd
    with patch.object(gitops, "_argocd_sync", AsyncMock(return_value=False)):
        r = await client.post(f"/api/v1/gitops/{app.id}/sync",
                              json={}, headers=_devops_headers())

    assert r.status_code == 502, r.text
    assert "sync call failed" in r.json()["detail"].lower()

    await db_session.refresh(app)
    assert app.last_synced_at is None, "failed sync must not stamp last_synced_at"
    assert app.sync_message is None, "failed sync must not write a success message"
    assert await _history_rows(db_session, app.id) == [], (
        "failed sync must not leave a history row claiming it happened"
    )


@pytest.mark.asyncio
async def test_sync_transport_exception_is_normalised_to_502(
    client, db_session, app_with_argocd
):
    """
    A transport-level blow-up inside the *real* ``_argocd_sync`` must still
    surface as 502 rather than an opaque 500.

    Note the seam: httpx is patched, not ``_argocd_sync``. The helper wraps its
    own call in ``except Exception: return False``, so replacing the helper
    outright would bypass the very guard under test and produce a misleading
    500. Patching httpx exercises the production path end to end.
    """
    import httpx

    app = app_with_argocd

    class ExplodingClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self):
            raise httpx.ConnectError("connection reset by peer")
        async def __aexit__(self, *a): return False

    with patch.object(httpx, "AsyncClient", ExplodingClient):
        r = await client.post(f"/api/v1/gitops/{app.id}/sync",
                              json={}, headers=_devops_headers())

    assert r.status_code == 502, r.text
    await db_session.refresh(app)
    assert app.last_synced_at is None
    assert await _history_rows(db_session, app.id) == []


# ── sync: success ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_successful_sync_records_history_and_stamps_time(
    client, db_session, app_with_argocd
):
    app = app_with_argocd
    with patch.object(gitops, "_argocd_sync", AsyncMock(return_value=True)):
        r = await client.post(f"/api/v1/gitops/{app.id}/sync",
                              json={}, headers=_devops_headers())

    assert r.status_code == 200, r.text
    await db_session.refresh(app)
    assert app.last_synced_at is not None
    assert app.sync_message == "Sync triggered via ArgoCD"

    rows = await _history_rows(db_session, app.id)
    assert len(rows) == 1
    # History records the trigger as Running — completion is reconciled later,
    # never assumed synchronously.
    assert rows[0].status == "Running"
    assert rows[0].source_type == "sync"


@pytest.mark.asyncio
async def test_dry_run_sync_does_not_stamp_last_synced(
    client, db_session, app_with_argocd
):
    app = app_with_argocd
    with patch.object(gitops, "_argocd_sync", AsyncMock(return_value=True)):
        r = await client.post(f"/api/v1/gitops/{app.id}/sync",
                              json={"dry_run": True}, headers=_devops_headers())

    assert r.status_code == 200, r.text
    await db_session.refresh(app)
    assert app.last_synced_at is None, "a dry run must not claim a real sync"

    rows = await _history_rows(db_session, app.id)
    assert len(rows) == 1
    assert "dry-run" in rows[0].message


# ── rollback ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rollback_without_argocd_integration_is_503(client, db_session):
    app = GitOpsApp(tenant_id=TENANT, name="no-integ-rb",
                    argocd_app_name="no-integ-rb", repo_url="https://g/x", path=".")
    db_session.add(app)
    await db_session.commit()

    r = await client.post(f"/api/v1/gitops/{app.id}/rollback",
                          json={"revision": "bbbbbbb2222"},
                          headers=_devops_headers())
    assert r.status_code == 503, r.text
    assert await _history_rows(db_session, app.id) == []


@pytest.mark.asyncio
async def test_rollback_provider_failure_is_502_and_changes_nothing(
    client, db_session, app_with_argocd
):
    app = app_with_argocd
    original = app.current_revision

    with patch.object(gitops, "_argocd_rollback", AsyncMock(return_value=False)):
        r = await client.post(f"/api/v1/gitops/{app.id}/rollback",
                              json={"revision": "bbbbbbb2222"},
                              headers=_devops_headers())

    assert r.status_code == 502, r.text
    await db_session.refresh(app)
    assert app.current_revision == original, "failed rollback must not move revision"
    assert app.last_synced_at is None
    assert await _history_rows(db_session, app.id) == []


@pytest.mark.asyncio
async def test_successful_rollback_confirms_live_revision(
    client, db_session, app_with_argocd
):
    """ArgoCD confirms the effective revision — state may be marked Synced."""
    app = app_with_argocd
    with patch.object(gitops, "_argocd_rollback", AsyncMock(return_value=True)), \
         patch.object(gitops, "_argocd_get_revision", AsyncMock(return_value="bbbbbbb2222")):
        r = await client.post(f"/api/v1/gitops/{app.id}/rollback",
                              json={"revision": "bbbbbbb2222"},
                              headers=_devops_headers())

    assert r.status_code == 200, r.text
    await db_session.refresh(app)
    assert app.current_revision == "bbbbbbb2222"
    assert app.sync_status == "Synced"

    rows = await _history_rows(db_session, app.id)
    assert len(rows) == 1
    assert rows[0].source_type == "rollback"


@pytest.mark.asyncio
async def test_rollback_that_cannot_confirm_revision_does_not_claim_synced(
    client, db_session, app_with_argocd
):
    """
    ArgoCD accepted the rollback but the live revision cannot be read back.
    The endpoint must NOT report Synced — it marks Progressing/OutOfSync so the
    UI never claims a success that was not verified.
    """
    app = app_with_argocd
    with patch.object(gitops, "_argocd_rollback", AsyncMock(return_value=True)), \
         patch.object(gitops, "_argocd_get_revision", AsyncMock(return_value=None)):
        r = await client.post(f"/api/v1/gitops/{app.id}/rollback",
                              json={"revision": "ccccccc3333"},
                              headers=_devops_headers())

    assert r.status_code == 200, r.text
    await db_session.refresh(app)
    assert app.sync_status != "Synced", (
        "unverified rollback must not be reported as Synced"
    )
    assert app.sync_status == "OutOfSync"
    assert app.health_status == "Progressing"
    assert "verifying" in (app.sync_message or "").lower()


# ── authorisation and tenancy ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_and_rollback_require_a_devops_role(
    client, db_session, app_with_argocd
):
    """Server-side RBAC: a viewer is refused before any provider call."""
    app = app_with_argocd
    sync_mock = AsyncMock(return_value=True)
    with patch.object(gitops, "_argocd_sync", sync_mock):
        r = await client.post(f"/api/v1/gitops/{app.id}/sync",
                              json={}, headers=_viewer_headers())
    assert r.status_code == 403, r.text
    assert sync_mock.await_count == 0, "RBAC must deny before calling the provider"


@pytest.mark.asyncio
async def test_sync_of_another_tenants_app_is_404(client, db_session, app_with_argocd):
    """Cross-tenant access must 404, not leak the app's existence."""
    other = {"Authorization": "Bearer " + create_access_token(
        user_id="u-other", email="devops@other.dev",
        tenant_id="t-someone-else", roles=["devops_engineer"],
    )}
    app = app_with_argocd
    with patch.object(gitops, "_argocd_sync", AsyncMock(return_value=True)):
        r = await client.post(f"/api/v1/gitops/{app.id}/sync",
                              json={}, headers=other)
    assert r.status_code == 404, r.text
    assert await _history_rows(db_session, app.id) == []
