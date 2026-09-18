"""P1.6-SECRET-1 — 422 validation errors must never echo secret inputs.

Pre-fix (live): register with a password but missing email returned 422 whose
`input` field contained the plaintext password.  Pydantic v2 includes the
offending body by default.  Post-fix: detail items carry only type/loc/msg.
"""
import pytest


@pytest.mark.asyncio
async def test_register_422_does_not_echo_password(client):
    r = await client.post("/api/v1/auth/register", json={
        "username": "px", "password": "SECRET-PASS-1234!", "full_name": "X"})
    assert r.status_code == 422
    assert "SECRET-PASS" not in r.text, "plaintext password echoed in 422"
    assert '"input"' not in r.text, "raw input must not be serialized"
    # contract kept: structured detail list
    assert isinstance(r.json()["detail"], list)


@pytest.mark.asyncio
async def test_integration_credentials_not_echoed_on_422(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "sec-a@test.dev", "username": "seca", "full_name": "A",
        "password": "Str0ng!Pass9", "company_name": "OrgSec"})
    tok = r.json()["data"]["access_token"]
    r = await client.post("/api/v1/integrations",
        headers={"Authorization": f"Bearer {tok}"},
        json={"name": "x", "credentials": {"token": "ghp_SUPPOSEDLY_SECRET_ABC123"}})  # missing `type` → 422
    assert r.status_code == 422
    assert "ghp_SUPPOSEDLY_SECRET_ABC123" not in r.text, "credential echoed in 422"


@pytest.mark.asyncio
async def test_login_422_contract_still_structured(client):
    r = await client.post("/api/v1/auth/login", json={"password": "Shh-Dont-Echo-9"})
    assert r.status_code == 422
    assert "Shh-Dont-Echo" not in r.text
    assert {"type", "loc", "msg"} <= set(r.json()["detail"][0].keys())
