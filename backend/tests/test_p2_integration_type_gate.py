"""P2 §13 fake-success removal — BUG-P2-03 regression.

Proven live in P2 battery: POST /api/v1/integrations accepted
``type: totally-bogus-provider`` (201).  ``IntegrationService._build_client``
then fell into a `_NoOpIntegration` stub and ``test_connection`` crashed on a
missing attribute, landing in the catch-all with
``error_message = "'_NoOpIntegration' object has no attribute
'get_authenticated_user'"`` — an implementation-traceback leak to the UI, and
a structured fake-provider acceptance path.

Fix (root cause): (a) unsupported types are rejected at the schema boundary
with 422, (b) the NoOp stub is deleted — ``_build_client`` raises for unknown
types, (c) any internal error in test_connection no longer echoes raw
exception text — only provider-shaped messages (status-typed GitHubAPIError
etc.) may flow out.
"""
import pytest


async def _register(client, email: str, org: str):
    username = email.split("@")[0].replace("-", "_")
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "full_name": "Admin",
        "password": "Str0ng!Pass9", "company_name": org,
    })
    assert r.status_code in (200, 201), r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_unknown_integration_type_rejected_422(client):
    h = await _register(client, "p2-type-gate@test.dev", "OrgTypeGate")
    r = await client.post("/api/v1/integrations", headers=h, json={
        "name": "bogus-provider", "type": "totally-bogus-provider",
        "credentials": {"api_key": "x"}, "config": {},
    })
    assert r.status_code == 422, f"expected 422 for unknown type, got {r.status_code}: {r.text[:200]}"


@pytest.mark.asyncio
async def test_supported_types_still_accepted(client):
    h = await _register(client, "p2-type-ok@test.dev", "OrgTypeOk")
    for t in ("github", "gitlab", "aws", "kubernetes", "stripe"):
        r = await client.post("/api/v1/integrations", headers=h, json={
            "name": f"ok-{t}", "type": t, "credentials": {}, "config": {},
        })
        assert r.status_code in (200, 201), f"{t} unexpectedly rejected: {r.status_code} {r.text[:150]}"


@pytest.mark.asyncio
async def test_noop_stub_is_gone():
    from app.services.integration_service import IntegrationService
    with pytest.raises((ValueError, KeyError)):
        IntegrationService._build_client("not-a-provider", {}, {})


@pytest.mark.asyncio
async def test_internal_error_never_leaks_traceback(client):
    """Even if something internal explodes, error_message must not contain a
    Python traceback shape (this was the live evidence for BUG-P2-03)."""
    h = await _register(client, "p2-novleak@test.dev", "OrgLeakGate")
    # create a real-type integration with crudentials that will 401 fast
    r = await client.post("/api/v1/integrations", headers=h, json={
        "name": "leak-probe", "type": "github",
        "credentials": {"token": "ghp_nope"}, "config": {},
    })
    assert r.status_code in (200, 201), r.text
    iid = r.json()["data"]["id"]
    t = await client.post(f"/api/v1/integrations/{iid}/test", headers=h)
    row = await client.get(f"/api/v1/integrations/{iid}", headers=h)
    em = (row.json().get("data") or {}).get("error_message") or ""
    assert "object has no attribute" not in em
    assert "Traceback" not in em
    assert "_NoOpIntegration" not in em
