"""P1.5-WEBHOOK-1 regression — inbound webhooks must verify FAIL-CLOSED.

Handlers mutate tenant-owned DB rows, so an unverifiable request must never
reach them.  Contract per provider (github/gitlab/slack), mirroring stripe:
  secret unset            → 503 (not configured, never process)
  signed headers missing  → 401
  forged signature/token  → 401
  (slack) non-int ts      → 401  (was a total bypass via `except: pass`)
  properly signed request → passes verification and reaches the handlers (200)
"""
import hashlib
import hmac
import json
import time

import pytest

from app.config import settings


def _gh_sig(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
class TestGitHubWebhookFailClosed:
    async def test_secret_unset_rejects(self, client, monkeypatch):
        monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "")
        r = await client.post("/webhooks/github", json={}, headers={"X-GitHub-Event": "push"})
        assert r.status_code == 503

    async def test_missing_signature_rejects(self, client, monkeypatch):
        monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "s3cret")
        r = await client.post("/webhooks/github", json={}, headers={"X-GitHub-Event": "push"})
        assert r.status_code == 401

    async def test_forged_signature_rejects(self, client, monkeypatch):
        monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "s3cret")
        r = await client.post(
            "/webhooks/github", json={},
            headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": "sha256=deadbeef"},
        )
        assert r.status_code == 401

    async def test_valid_signature_accepted(self, client, monkeypatch):
        body = json.dumps({"repository": {"full_name": "no/such"}, "commits": []}).encode()
        monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "s3cret")
        r = await client.post(
            "/webhooks/github", content=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": _gh_sig("s3cret", body),
            },
        )
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
class TestGitLabWebhookFailClosed:
    async def test_secret_unset_rejects(self, client, monkeypatch):
        monkeypatch.setattr(settings, "GITLAB_WEBHOOK_SECRET", "")
        r = await client.post("/webhooks/gitlab", json={})
        assert r.status_code == 503

    async def test_missing_token_rejects(self, client, monkeypatch):
        monkeypatch.setattr(settings, "GITLAB_WEBHOOK_SECRET", "gl-secret")
        r = await client.post("/webhooks/gitlab", json={})
        assert r.status_code == 401

    async def test_forged_token_rejects(self, client, monkeypatch):
        monkeypatch.setattr(settings, "GITLAB_WEBHOOK_SECRET", "gl-secret")
        r = await client.post("/webhooks/gitlab", json={}, headers={"X-Gitlab-Token": "wrong"})
        assert r.status_code == 401

    async def test_valid_token_accepted(self, client, monkeypatch):
        monkeypatch.setattr(settings, "GITLAB_WEBHOOK_SECRET", "gl-secret")
        r = await client.post(
            "/webhooks/gitlab", json={"object_kind": "push"},
            headers={"X-Gitlab-Token": "gl-secret", "X-Gitlab-Event": "Push Hook"},
        )
        assert r.status_code == 200, r.text

    async def test_github_secret_no_longer_accepted(self, client, monkeypatch):
        """Copy-paste regression: the GITHUB secret must never open the GitLab hook."""
        monkeypatch.setattr(settings, "GITLAB_WEBHOOK_SECRET", "gl-secret")
        monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "gh-secret")
        r = await client.post("/webhooks/gitlab", json={}, headers={"X-Gitlab-Token": "gh-secret"})
        assert r.status_code == 401


@pytest.mark.asyncio
class TestSlackWebhookFailClosed:
    async def test_secret_unset_rejects(self, client, monkeypatch):
        monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "")
        r = await client.post("/webhooks/slack", json={"type": "x"})
        assert r.status_code == 503

    async def test_missing_headers_reject(self, client, monkeypatch):
        monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "sig-secret")
        r = await client.post("/webhooks/slack", json={"type": "x"})
        assert r.status_code == 401

    async def test_forged_signature_rejects(self, client, monkeypatch):
        monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "sig-secret")
        r = await client.post(
            "/webhooks/slack", json={"type": "x"},
            headers={"X-Slack-Signature": "v0=deadbeef",
                     "X-Slack-Request-Timestamp": str(int(time.time()))},
        )
        assert r.status_code == 401

    async def test_non_integer_timestamp_rejects(self, client, monkeypatch):
        """Was a total verification bypass via `except Exception: pass`."""
        monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "sig-secret")
        r = await client.post(
            "/webhooks/slack", json={"type": "x"},
            headers={"X-Slack-Signature": "v0=whatever",
                     "X-Slack-Request-Timestamp": "not-a-number"},
        )
        assert r.status_code == 401

    async def test_stale_timestamp_rejects(self, client, monkeypatch):
        monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "sig-secret")
        r = await client.post(
            "/webhooks/slack", json={"type": "x"},
            headers={"X-Slack-Signature": "v0=whatever",
                     "X-Slack-Request-Timestamp": str(int(time.time()) - 900)},
        )
        assert r.status_code == 401

    async def test_valid_signature_accepted(self, client, monkeypatch):
        body = json.dumps({"type": "app_mention", "event": {"text": "hi"}}).encode()
        ts = str(int(time.time()))
        monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "sig-secret")
        base = f"v0:{ts}:{body.decode()}".encode()
        sig = "v0=" + hmac.new(b"sig-secret", base, hashlib.sha256).hexdigest()
        r = await client.post(
            "/webhooks/slack", content=body,
            headers={"Content-Type": "application/json",
                     "X-Slack-Signature": sig, "X-Slack-Request-Timestamp": ts},
        )
        assert r.status_code == 200, r.text
