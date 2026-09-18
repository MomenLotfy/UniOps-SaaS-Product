"""P1.5-GITLAB-1 regression — GitLab test-connection is now a real flow.

Previously the service's shared GitHub/GitLab branch called
client.get_authenticated_user(), a surface only GitHubClient implemented, so
every GitLab connection test died with AttributeError and never reached the
network.  These tests pin the fixed contract:

  happy path (200 + username)   → status connected, username in config
  401 from provider             → status invalid_token (provider-named message)
  transport error (unreachable) → status error with real exception text —
                                  NEVER an AttributeError leak again.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.github.client import GitHubAPIError
from app.services.integration_service import IntegrationService


class _Result:
    def __init__(self, obj=None):
        self._obj = obj
    def scalar_one_or_none(self):
        return self._obj


def _row():
    return SimpleNamespace(
        id="gl-1", tenant_id="t-1", name="gl", type="gitlab",
        status="pending", credentials={"token": "x"}, config={}, error_message=None,
    )


def _svc(db, client):
    svc = IntegrationService(db)
    svc._build_client = lambda *a, **k: client  # stub only the factory, not the flow
    return svc


def _db(row):
    db = MagicMock()
    db.execute = AsyncMock(return_value=_Result(row))
    db.flush = AsyncMock(); db.commit = AsyncMock(); db.rollback = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_gitlab_success_marks_connected():
    row = _row(); db = _db(row)
    client = SimpleNamespace(
        get_authenticated_user=AsyncMock(return_value={"login": "janedoe", "id": 7})
    )
    result = await _svc(db, client).test_connection("gl-1")
    assert result.success is True
    assert row.status == "connected"
    assert row.config.get("username") == "janedoe"


@pytest.mark.asyncio
async def test_gitlab_401_maps_invalid_token():
    row = _row(); db = _db(row)
    client = SimpleNamespace(
        get_authenticated_user=AsyncMock(side_effect=GitHubAPIError(401, "401 Unauthorized"))
    )
    result = await _svc(db, client).test_connection("gl-1")
    assert result.success is False
    assert row.status == "invalid_token"
    assert "GitLab" in row.error_message          # provider-named, not "GitHub"
    assert "get_authenticated_user" not in row.error_message


@pytest.mark.asyncio
async def test_gitlab_transport_error_never_leaks_attribute_error():
    row = _row(); db = _db(row)
    client = SimpleNamespace(
        get_authenticated_user=AsyncMock(side_effect=GitHubAPIError(0, "connection refused"))
    )
    result = await _svc(db, client).test_connection("gl-1")
    assert result.success is False
    assert row.status == "error"
    assert row.error_message == "connection refused"
    assert "attribute" not in (row.error_message or "").lower()


def test_gitlab_client_implements_authenticated_user_surface():
    """Interface pin — the branch's required contract exists on the real client.

    Fails on pre-fix code (GitLabClient lacked get_authenticated_user entirely),
    independent of any stubbed service-level tests above."""
    from app.integrations.gitlab.client import GitLabClient
    client = GitLabClient({"token": "x"})
    assert callable(getattr(client, "get_authenticated_user", None))
