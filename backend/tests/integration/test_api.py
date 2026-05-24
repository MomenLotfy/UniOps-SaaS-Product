"""Integration tests for the FastAPI HTTP layer."""
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
class TestHealthEndpoints:
    async def test_health_returns_ok(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

    async def test_health_ready_returns_200(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health/ready")
        assert response.status_code == 200


@pytest.mark.asyncio
class TestAuthRequired:
    async def test_users_endpoint_requires_auth(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/users")
        assert response.status_code in (401, 403)

    async def test_integrations_requires_auth(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/integrations")
        assert response.status_code in (401, 403)

    async def test_invalid_token_returns_401(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/users",
                headers={"Authorization": "Bearer invalid_token_here"},
            )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestWebhookEndpoints:
    async def test_github_webhook_without_secret(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/webhooks/github",
                json={"action": "workflow_run"},
                headers={"X-GitHub-Event": "workflow_run"},
            )
        assert response.status_code in (200, 401)

    async def test_stripe_webhook_requires_signature(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/webhooks/stripe",
                content=b'{"type": "invoice.payment_succeeded"}',
                headers={"Content-Type": "application/json"},
            )
        assert response.status_code in (400, 500)


@pytest.mark.asyncio
class TestOpenAPISchema:
    async def test_openapi_json_available(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "/health" in schema["paths"] or "/api/v1/health" in schema["paths"] or any(
            k.endswith("/health") for k in schema["paths"]
        )
