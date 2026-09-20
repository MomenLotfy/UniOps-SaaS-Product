"""
Audit-trail coverage for the GitOps mutations.

The pod mutations audit explicitly inside ``KubernetesService._write_audit``, but
the GitOps endpoints contain no audit code at all — a grep of ``gitops.py`` for
``AuditLog`` / ``_write_audit`` returns nothing. That looks like a gap until you
find ``AuditMiddleware`` (``app/middleware/audit.py``), which logs every
POST/PUT/PATCH/DELETE with actor, tenant, action, resource and a result derived
from the response status.

So GitOps mutations ARE audited, just at a different layer. This file locks that
in, because a middleware-level guarantee is easy to break silently: reordering
``add_middleware`` calls, adding a path prefix to ``AUDIT_EXCLUDED_PREFIXES``, or
making the auth middleware stop populating ``request.state.user_id`` would all
stop the audit trail without failing any other test.

The important assertion is the failure case: a sync the provider rejected must be
recorded as ``status="failure"``, not as a success and not as nothing at all.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.models.gitops_app import GitOpsApp
from app.models.integration import Integration

TENANT = "t-argocd-audit"


@pytest.fixture(autouse=True)
def _bind_audit_middleware_to_test_db(monkeypatch):
    """
    ``AuditMiddleware`` resolves ``app.core.database.AsyncSessionLocal`` lazily
    inside ``dispatch``, so it writes to ``settings.DATABASE_URL`` — the dev
    database — rather than the test engine the ``client`` fixture overrides via
    ``get_db``. Without this, audit rows land in the real dev DB and the test
    reads an empty table.

    Only the session factory is rebound; the middleware's own logic (path
    parsing, action naming, status derivation, AuditService.log) still runs for
    real, which is what this file is meant to prove.
    """
    import app.core.database as core_db
    from tests.conftest import TestSessionLocal

    monkeypatch.setattr(core_db, "AsyncSessionLocal", TestSessionLocal)


def _devops_headers() -> dict:
    return {"Authorization": "Bearer " + create_access_token(
        user_id="u-argocd-audit", email="devops@audit.dev",
        tenant_id=TENANT, roles=["devops_engineer"],
    )}


@pytest.fixture
async def app_with_argocd(client, db_session):
    integ = Integration(
        tenant_id=TENANT, name="argocd-prod", type="argocd",
        is_active=True, status="connected",
        credentials={"server_url": "https://argocd.example", "token": "tok-123"},
    )
    app = GitOpsApp(
        tenant_id=TENANT, name="payments", argocd_app_name="payments",
        repo_url="https://github.com/acme/payments", path=".",
        namespace="prod", current_revision="aaaaaaaaaaa1111",
    )
    db_session.add_all([integ, app])
    await db_session.commit()
    return app


async def _audit_rows(db_session) -> list:
    r = await db_session.execute(
        select(AuditLog).where(AuditLog.tenant_id == TENANT)
        .order_by(AuditLog.created_at.desc())
    )
    return list(r.scalars().all())


@pytest.mark.asyncio
async def test_failed_sync_is_audited_as_failure(
    client, db_session, app_with_argocd, monkeypatch
):
    """
    The provider rejects the sync (502). The audit trail must record it — with
    the actor, the tenant, the action and a failure result.
    """
    from unittest.mock import AsyncMock, patch
    from app.api.v1.endpoints import gitops

    app = app_with_argocd
    with patch.object(gitops, "_argocd_sync", AsyncMock(return_value=False)):
        r = await client.post(f"/api/v1/gitops/{app.id}/sync",
                              json={}, headers=_devops_headers())
    assert r.status_code == 502, r.text

    rows = await _audit_rows(db_session)
    sync_rows = [x for x in rows if x.action.endswith("sync")]
    assert sync_rows, (
        f"a failed sync produced no audit row; actions seen: "
        f"{[x.action for x in rows]}"
    )
    row = sync_rows[0]
    assert row.status == "failure", (
        f"a provider-rejected sync must audit as failure, got {row.status!r}"
    )
    # actor + tenant + resource, per the audit contract
    assert row.user_id == "u-argocd-audit"
    assert row.tenant_id == TENANT
    assert row.resource_id == app.id


@pytest.mark.asyncio
async def test_successful_sync_is_audited_as_success(
    client, db_session, app_with_argocd
):
    from unittest.mock import AsyncMock, patch
    from app.api.v1.endpoints import gitops

    app = app_with_argocd
    with patch.object(gitops, "_argocd_sync", AsyncMock(return_value=True)):
        r = await client.post(f"/api/v1/gitops/{app.id}/sync",
                              json={}, headers=_devops_headers())
    assert r.status_code == 200, r.text

    rows = await _audit_rows(db_session)
    sync_rows = [x for x in rows if x.action.endswith("sync")]
    assert sync_rows, "a successful sync produced no audit row"
    assert sync_rows[0].status == "success"


@pytest.mark.asyncio
async def test_failed_rollback_is_audited_as_failure(
    client, db_session, app_with_argocd
):
    from unittest.mock import AsyncMock, patch
    from app.api.v1.endpoints import gitops

    app = app_with_argocd
    with patch.object(gitops, "_argocd_rollback", AsyncMock(return_value=False)):
        r = await client.post(f"/api/v1/gitops/{app.id}/rollback",
                              json={"revision": "bbbbbbb2222"},
                              headers=_devops_headers())
    assert r.status_code == 502, r.text

    rows = await _audit_rows(db_session)
    rb = [x for x in rows if x.action.endswith("rollback")]
    assert rb, f"a failed rollback produced no audit row; seen {[x.action for x in rows]}"
    assert rb[0].status == "failure"
    assert rb[0].user_id == "u-argocd-audit"


@pytest.mark.asyncio
async def test_audit_rows_leak_no_credentials(
    client, db_session, app_with_argocd
):
    """
    The ArgoCD token and server URL must not end up in the audit trail, which is
    readable by auditors who have no business holding deployment credentials.
    """
    from unittest.mock import AsyncMock, patch
    from app.api.v1.endpoints import gitops

    app = app_with_argocd
    with patch.object(gitops, "_argocd_sync", AsyncMock(return_value=True)):
        await client.post(f"/api/v1/gitops/{app.id}/sync",
                          json={}, headers=_devops_headers())

    rows = await _audit_rows(db_session)
    assert rows, "expected at least one audit row"
    blob = repr([(r.action, r.resource, r.resource_id, r.details) for r in rows]).lower()
    for secret in ("tok-123", "argocd.example", "authorization", "bearer",
                   "kubeconfig", "password"):
        assert secret not in blob, f"audit trail leaked {secret!r}: {blob}"
