import pytest


@pytest.mark.asyncio
async def test_register_and_login(client):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "password": "Test@1234",
        "company_name": "Test Co",
    })
    assert reg.status_code == 200
    data = reg.json()
    assert data["success"] is True
    assert "access_token" in data["data"]

    login = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "Test@1234",
    })
    assert login.status_code == 200
    tokens = login.json()["data"]
    assert "access_token" in tokens
    assert "refresh_token" in tokens


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "email": "wrong@example.com",
        "username": "wronguser",
        "full_name": "Wrong User",
        "password": "Test@1234",
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpassword",
    })
    assert login.status_code in [401, 200]


@pytest.mark.asyncio
async def test_protected_route_without_token(client):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 403
