import pytest


@pytest.mark.asyncio
async def test_list_integrations_unauthenticated(client):
    response = await client.get("/api/v1/integrations")
    # Missing credentials → 401 Unauthorized (not 403: that's for
    # authenticated-but-insufficient-role)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_endpoint_structure(client):
    response = await client.get("/health")
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
