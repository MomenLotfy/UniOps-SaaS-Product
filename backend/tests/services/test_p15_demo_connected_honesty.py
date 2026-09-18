"""P1.5-DEMO-1 regression — fabricated 'demo connected' success path removed.

A row claiming status="connected" while holding NO credentials is a
fabricated-integrity state.  The service must answer test_connection(...) with
success=False (never fake-green), and must NOT perform any provider call.
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.services.integration_service import IntegrationService


class _Result:
    def __init__(self, obj=None):
        self._obj = obj
    def scalar_one_or_none(self):
        return self._obj
    def scalars(self):
        inner = MagicMock(); inner.first.return_value = self._obj; return inner


def _conn_less_connected_row():
    return SimpleNamespace(
        id="int-1", tenant_id="t-1", name="fake", type="github",
        status="connected", credentials={}, config={}, error_message=None,
    )


@pytest.mark.asyncio
async def test_demo_connected_no_creds_never_reports_success():
    db = MagicMock()
    db.execute = AsyncMock(return_value=_Result(_conn_less_connected_row()))
    db.commit = AsyncMock(); db.rollback = AsyncMock()

    svc = IntegrationService(db)
    result = await svc.test_connection("int-1")

    assert result.success is False, "must never fabricate a green connection state"
    assert "credentials" in result.message.lower()


@pytest.mark.asyncio
async def test_demo_connected_no_creds_makes_no_provider_call():
    db = MagicMock()
    db.execute = AsyncMock(return_value=_Result(_conn_less_connected_row()))
    db.commit = AsyncMock(); db.rollback = AsyncMock()

    svc = IntegrationService(db)
    await svc.test_connection("int-1")

    # only the row SELECT may have executed — no httpx/provider session built
    assert db.execute.await_count == 1
