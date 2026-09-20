"""BUG-001 — GitHub CI/CD mutation regression tests.

Before the fix, ``rerun_workflow_run``, ``rerun_failed_jobs`` and
``cancel_workflow_run`` read ``self._headers``, an attribute that was never
assigned, so every call raised AttributeError before issuing any HTTP request.

These tests use a stubbed httpx transport — no real GitHub token required.
"""
from __future__ import annotations

import httpx
import pytest

from app.integrations.github.client import GitHubAPIError, GitHubClient

TOKEN = "ghp_unit_test_token_not_real"


def make_client(status_code: int, body: bytes = b"{}", token: str = TOKEN):
    """Build a GitHubClient whose requests hit a MockTransport."""
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(
            status_code, content=body,
            headers={"content-type": "application/json"},
        )

    client = GitHubClient({"token": token})

    async def patched_request(method, path, params=None, json=None,
                              raw=False, timeout=15):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as c:
            r = await c.request(
                method, f"https://api.github.com{path}",
                headers=client._build_headers(), params=params, json=json,
            )
        if raw:
            return r
        if r.status_code != 200:
            try:
                message = r.json().get("message", f"HTTP {r.status_code}")
            except Exception:
                message = str(r.text)
            raise GitHubAPIError(r.status_code, message)
        return r.json()

    client._request = patched_request
    return client, sent


# ── 1-3. Every mutation sends the Authorization header ───────────────────────

@pytest.mark.parametrize("method,path_suffix,ok_status", [
    ("rerun_workflow_run",  "/rerun",             201),
    ("rerun_failed_jobs",   "/rerun-failed-jobs", 201),
    # GitHub answers cancel with 202 Accepted, not 201
    ("cancel_workflow_run", "/cancel",            202),
])
@pytest.mark.asyncio
async def test_mutation_sends_authorization_header(method, path_suffix, ok_status):
    client, sent = make_client(ok_status)
    result = await getattr(client, method)("audit-org", "api", 4242)

    assert result["success"] is True
    assert result["run_id"] == 4242

    assert len(sent) == 1, "exactly one HTTP request must be issued"
    req = sent[0]
    assert req.headers["authorization"] == f"Bearer {TOKEN}"
    assert req.headers["accept"] == "application/vnd.github+json"
    assert req.url.path == (
        f"/repos/audit-org/api/actions/runs/4242{path_suffix}"
    )


@pytest.mark.asyncio
async def test_cancel_accepts_202():
    client, _ = make_client(202, b"")
    result = await client.cancel_workflow_run("o", "r", 7)
    assert result["success"] is True


# ── 4. Success is mapped correctly ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_rerun_success_maps_to_success_true():
    client, _ = make_client(201)
    assert (await client.rerun_workflow_run("o", "r", 1))["success"] is True


# ── 5. Failure is mapped correctly ──────────────────────────────────────────

@pytest.mark.parametrize("status,body,expected", [
    (403, b'{"message":"Must have admin rights"}', "Must have admin rights"),
    (404, b'{"message":"Not Found"}',              "Not Found"),
    (409, b'{"message":"Already running"}',        "Already running"),
    (422, b'{"message":"unprocessable"}',          "unprocessable"),
])
@pytest.mark.asyncio
async def test_github_error_status_maps_to_success_false(status, body, expected):
    client, _ = make_client(status, body)
    result = await client.cancel_workflow_run("o", "r", 1)
    assert result["success"] is False
    assert result["error"] == expected


@pytest.mark.asyncio
async def test_error_body_without_message_falls_back_to_status():
    client, _ = make_client(500, b"not json")
    result = await client.rerun_workflow_run("o", "r", 1)
    assert result["success"] is False
    assert "500" in result["error"]


# ── 6. Missing credentials must not raise AttributeError ────────────────────

@pytest.mark.parametrize("method", [
    "rerun_workflow_run", "rerun_failed_jobs", "cancel_workflow_run",
])
@pytest.mark.asyncio
async def test_missing_token_is_a_clean_failure_not_attribute_error(method):
    client, sent = make_client(201, token="")
    result = await getattr(client, method)("o", "r", 1)

    assert result["success"] is False
    assert "Missing GitHub token" in result["error"]
    assert len(sent) == 0, "no request may be sent without credentials"


@pytest.mark.parametrize("method", [
    "rerun_workflow_run", "rerun_failed_jobs", "cancel_workflow_run",
])
@pytest.mark.asyncio
async def test_no_client_exposes_a_stale_headers_attribute(method):
    """The defect was a never-assigned ``self._headers``; assert it is gone."""
    client = GitHubClient({"token": TOKEN})
    assert not hasattr(client, "_headers")
    assert callable(client._build_headers)


# ── 7. No secret is logged ──────────────────────────────────────────────────

@pytest.mark.parametrize("method", [
    "rerun_workflow_run", "rerun_failed_jobs", "cancel_workflow_run",
])
@pytest.mark.asyncio
async def test_token_never_appears_in_logs(method, caplog):
    client, _ = make_client(403, b'{"message":"nope"}')
    with caplog.at_level("DEBUG"):
        await getattr(client, method)("o", "r", 1)

    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert TOKEN not in blob, "GitHub token leaked into a log record"
    assert "Bearer" not in blob, "Authorization value leaked into a log record"


# ── Header construction is centralised ──────────────────────────────────────

@pytest.mark.asyncio
async def test_headers_are_rebuilt_when_the_token_changes():
    """No cached header state: a rotated token is used immediately."""
    client, sent = make_client(201)
    await client.rerun_workflow_run("o", "r", 1)
    assert sent[-1].headers["authorization"] == f"Bearer {TOKEN}"

    client.token = "ghp_rotated_token"
    await client.rerun_workflow_run("o", "r", 2)
    assert sent[-1].headers["authorization"] == "Bearer ghp_rotated_token"
