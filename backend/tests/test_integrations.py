import pytest


@pytest.mark.asyncio
async def test_list_integrations_unauthenticated(client):
    response = await client.get("/api/v1/integrations")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_health_endpoint_structure(client):
    response = await client.get("/health")
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
