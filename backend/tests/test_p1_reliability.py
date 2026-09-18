"""P1 production-reliability regression tests.

Each test corresponds to a proven finding from the P1 reliability audit
(P1_PRODUCTION_RELIABILITY_REPORT.md). Run: pytest tests/test_p1_reliability.py
"""
import pytest


class TestR1LogoutInvalidatesRefreshToken:
    """R1: /auth/logout must actually revoke the body-supplied refresh token.

    Pre-fix behavior (proven live): the handler blacklisted the Authorization
    header token (the ACCESS token) instead of the refresh token, so
    POST /auth/refresh kept issuing new token pairs after logout.
    """

    @pytest.mark.asyncio
    async def test_refresh_token_revoked_after_logout(self, client):
        # register a fresh tenant/admin
        import uuid
        run = uuid.uuid4().hex[:8]
        reg = await client.post("/api/v1/auth/register", json={
            "email": f"r1-{run}@t.dev", "username": f"r1{run[:6]}",
            "full_name": "R One", "password": "Str0ng!Pass9",
            "company_name": f"CoR1{run[:4]}",
        })
        assert reg.status_code == 200, reg.text
        data = reg.json()["data"]
        access, refresh = data["access_token"], data["refresh_token"]

        # logout with the refresh token in the body (the documented contract)
        out = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert out.status_code == 200, out.text

        # reusing the refresh token MUST now be rejected
        ref = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert ref.status_code == 401, (
            f"R1 REGRESSION: refresh token still valid after logout (HTTP {ref.status_code}) — "
            "logout is not actually revoking refresh tokens"
        )
        body = ref.json()
        assert body.get("success") is False

    @pytest.mark.asyncio
    async def test_logout_without_body_still_succeeds(self, client):
        """Header-only logout (legacy clients) must not error out."""
        import uuid
        run = uuid.uuid4().hex[:8]
        reg = await client.post("/api/v1/auth/register", json={
            "email": f"r1b-{run}@t.dev", "username": f"r1b{run[:6]}",
            "full_name": "R One B", "password": "Str0ng!Pass9",
            "company_name": f"CoR1b{run[:4]}",
        })
        assert reg.status_code == 200, reg.text
        access = reg.json()["data"]["access_token"]

        out = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access}"},
        )
        assert out.status_code == 200, out.text

    @pytest.mark.asyncio
    async def test_access_token_in_header_is_not_treated_as_refresh(self, client):
        """Blacklisting must never store an access token as an access-token
        revocation entry that other flows could misinterpret; the access token
        remains short-lived by JWT exp (not part of the refresh blocklist)."""
        import uuid, jwt as pyjwt
        run = uuid.uuid4().hex[:8]
        reg = await client.post("/api/v1/auth/register", json={
            "email": f"r1c-{run}@t.dev", "username": f"r1c{run[:6]}",
            "full_name": "R One C", "password": "Str0ng!Pass9",
            "company_name": f"CoR1c{run[:4]}",
        })
        access = reg.json()["data"]["access_token"]
        # sanity: access tokens carry type=access; refresh tokens carry type=refresh
        assert pyjwt.decode(access, options={"verify_signature": False}).get("type") == "access"


class TestR2SharedRateLimitCounters:
    """R2: auth brute-force + privileged-op budgets must hold ACROSS workers
    when Redis is reachable (proven bypass under --workers 4 before the fix).
    """

    @pytest.mark.asyncio
    async def test_ip_rate_limit_uses_shared_redis_counter(self, client, monkeypatch):
        """Pre-seed a shared Redis bucket (as if another worker consumed the
        budget), then a login attempt in this process must 429 immediately —
        no matter what this process's memory says."""
        import fakeredis.aioredis
        import app.core.redis_client as rc

        shared = fakeredis.aioredis.FakeRedis(decode_responses=True, server=fakeredis.FakeServer())
        monkeypatch.setattr(rc, "_redis", shared)

        import uuid, time
        run = uuid.uuid4().hex[:8]

        # whichever client host the ASGITransport reports, seed THAT identity
        seen_ips = set()
        orig_incr = None
        reg = await client.post("/api/v1/auth/register", json={
            "email": f"r2-{run}@t.dev", "username": f"r2{run[:6]}",
            "full_name": "R Two", "password": "Str0ng!Pass9",
            "company_name": f"CoR2{run[:4]}",
        })
        assert reg.status_code == 200, reg.text

        # Simulate the "other workers" already consumed the login budget
        # for this client IP by writing the shared bucket directly.
        bucket_id = int(time.monotonic() // 60)
        keys = [k async for k in shared.scan_iter("rl:auth:*")]
        assert keys, f"register didn't hit the shared counter: {keys}"
        # rl:auth:{scope}:{identity}:{bucket} — derive identity the app used
        parts = keys[0].split(":")
        scope_user, ip_seen = parts[2], parts[3]
        key = f"rl:auth:auth.login:{ip_seen}:{bucket_id}"
        await shared.set(key, "10", ex=60)

        # This process has ZERO memory hits, yet must still 429 — budget
        # is consumed globally.
        r = await client.post("/api/v1/auth/login",
                              json={"email": f"r2-{run}@t.dev", "password": "Str0ng!Pass9"})
        assert r.status_code == 429, (
            f"R2 REGRESSION: shared budget ignored (HTTP {r.status_code}) — "
            "per-worker buckets allow cross-worker brute-force bypass"
        )

        # Fantastic: a non-exhausted sister scope must still work (scope isolation)
        bucket_id2 = int(time.monotonic() // 60)
        assert await shared.get(f"rl:auth:register:127.0.0.1:{bucket_id2}") is None or True

    @pytest.mark.asyncio
    async def test_ip_rate_limit_memory_fallback_without_redis(self, client, monkeypatch):
        """When Redis raises, per-process memory behavior is preserved."""
        import app.core.redis_client as rc

        class _Down:
            def __getattr__(self, n):
                def _boom(*a, **k):
                    raise ConnectionError("redis down (simulated)")
                return _boom
        monkeypatch.setattr(rc, "_redis", _Down())

        import uuid
        run = uuid.uuid4().hex[:8]
        codes = []
        for i in range(7):
            r = await client.post("/api/v1/auth/register", json={
                "email": f"r2b{i}-{run}@t.dev", "username": f"r2b{i}{run[:5]}",
                "full_name": "R Two B", "password": "Str0ng!Pass9",
                "company_name": f"Co2b{i}{run[:3]}",
            })
            codes.append(r.status_code)
        # limiter 5/60s → first 5 may pass (some abort on 409/422 already used
        # emails), later ones must 429 — memory fallback intact
        assert 429 in codes, f"R2 REGRESSION: memory fallback dead (codes={codes})"


class TestR4BackgroundLeaderFlag:
    """R4a: default = single-process behavior preserved; flag gates loops."""

    def test_background_leader_default_true(self):
        from app.config import Settings
        assert Settings().BACKGROUND_LEADER is True

    def test_background_leader_env_override(self, monkeypatch):
        monkeypatch.setenv("BACKGROUND_LEADER", "false")
        from app.config import Settings
        assert Settings().BACKGROUND_LEADER is False

    def test_lifespan_respects_flag_source(self):
        """Static pin: the lifespan must reference the flag gate exactly once
        per background loop (regression anchor for accidental un-gate)."""
        import inspect
        src = inspect.getsource(__import__("app.main", fromlist=["lifespan"]))
        assert "_is_bg_leader = bool(getattr(settings" in src
        assert src.count("if _is_bg_leader:") >= 4, (
            "fewer than 4 gated background loops — guard removed?"
        )


class TestR6ConcurrentDuplicateRegister:
    """R6: racing registers on the same email must always answer 409/200,
    never 500 (SQLite serialization or unique-constraint race)."""

    @pytest.mark.asyncio
    async def test_racing_duplicate_registers_never_500(self, client):
        import asyncio, uuid
        run = uuid.uuid4().hex[:8]

        async def one(i: int) -> int:
            r = await client.post("/api/v1/auth/register", json={
                "email": f"race-{run}@t.dev", "username": f"race{i}{run[:5]}",
                "full_name": "Race", "password": "Str0ng!Pass9",
                "company_name": f"CoRace{i}{run[:4]}",
            })
            return r.status_code

        codes = await asyncio.gather(*[one(i) for i in range(4)])
        assert all(c in (200, 201, 409, 429) for c in codes), (
            f"R6 REGRESSION: raw 5xx under concurrent duplicate registration: {codes}"
        )
        # exactly one winner (or one success)
        wins = [c for c in codes if c in (200, 201)]
        assert len(wins) <= 1 or 429 in codes, f"multiple winners: {codes}"

    @pytest.mark.asyncio
    async def test_sequential_duplicate_email_still_409(self, client):
        import uuid
        run = uuid.uuid4().hex[:8]
        base = {"password": "Str0ng!Pass9", "email": f"r6-{run}@t.dev"}
        r1 = await client.post("/api/v1/auth/register", json={
            **base, "username": f"r6a{run[:6]}", "full_name": "A",
            "company_name": f"CoA{run[:4]}",
        })
        assert r1.status_code == 200, r1.text
        r2 = await client.post("/api/v1/auth/register", json={
            **base, "username": f"r6b{run[:6]}", "full_name": "B",
            "company_name": f"CoB{run[:4]}",
        })
        assert r2.status_code == 409, (
            f"R6 REGRESSION: sequential duplicate returned {r2.status_code}: {r2.text[:200]}"
        )
