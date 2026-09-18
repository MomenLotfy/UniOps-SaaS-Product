"""BUG-P2-02 regression: GET /pipelines must return a SINGLE envelope.

Live evidence (P2 battery, tenant p2c): the endpoint declared
``response_model=APIResponse[PaginatedResponse]`` and returned
``APIResponse(data=paginated)`` — i.e. the wire payload was
``{"success": true, "data": {"success": true, "data": [...], "total": N, ...}}``
(double envelope), while every other list endpoint returns exactly one.
Fixed by returning the ``PaginatedResponse`` directly with
``response_model=PaginatedResponse[PipelineResponse]``.
This test locks the single-envelope contract.
"""
import jwt as pyjwt
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
async def test_pipeline_list_single_envelope(client):
    h = await _register(client, "p2-env@test.dev", "OrgP2Env")
    r = await client.get("/api/v1/pipelines?page=1&page_size=5", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()

    # Exactly ONE envelope: success + data(list) + pagination fields.
    assert body["success"] is True
    assert isinstance(body["data"], list), (
        f"double-wrapped envelope: data is {type(body['data']).__name__}, "
        f"keys={list(body['data'].keys()) if isinstance(body['data'], dict) else 'n/a'}"
    )
    for k in ("total", "page", "page_size", "pages"):
        assert isinstance(body[k], int)

    # And crucially the data payload must NOT be a second APIResponse.
    inner = body["data"]
    if inner:
        item = inner[0]
        assert "success" not in item
        assert {"id", "repository", "status"} <= set(item)
