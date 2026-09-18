"""P1.6-INVITE-1 — invitation redemption must bind tenant + role.

Pre-fix evidence (live/in-process): RegisterRequest had no invite_token field,
so every invitee silently registered as ADMIN of a NEW tenant while the invite
row sat unconsumed in Redis.  Post-fix: viewer redeems into the inviter's
tenant with the invited role, and the token is consumed (single-use).
"""
import pytest
import jwt


@pytest.mark.asyncio
async def test_invited_viewer_lands_in_inviting_tenant_with_invited_role(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "inv-a@test.dev", "username": "inva", "full_name": "A",
        "password": "Str0ng!Pass9", "company_name": "OrgInv"})
    assert r.status_code in (200, 201), r.text
    atok = r.json()["data"]["access_token"]
    aclaims = jwt.decode(atok, options={"verify_signature": False})

    ri = await client.post("/api/v1/users/invite",
                           headers={"Authorization": f"Bearer {atok}"},
                           json={"email": "inv-v@test.dev", "role": "viewer", "full_name": "V"})
    assert ri.status_code in (200, 201), ri.text
    itok = ri.json()["data"]["token"]

    rv = await client.post("/api/v1/auth/register", json={
        "email": "inv-v@test.dev", "username": "invv", "full_name": "V",
        "password": "Str0ng!Pass9", "invite_token": itok})
    assert rv.status_code in (200, 201), rv.text
    vclaims = jwt.decode(rv.json()["data"]["access_token"], options={"verify_signature": False})

    assert vclaims["tenant_id"] == aclaims["tenant_id"], \
        "invited user must join the inviter's tenant (pre-fix: fresh tenant)"
    assert vclaims.get("roles") == ["viewer"], \
        f"invited role must be enforced (pre-fix: silently 'admin'): {vclaims.get('roles')}"


@pytest.mark.asyncio
async def test_invite_token_single_use(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "inv2-a@test.dev", "username": "inv2a", "full_name": "A",
        "password": "Str0ng!Pass9", "company_name": "OrgInv2"})
    atok = r.json()["data"]["access_token"]
    ri = await client.post("/api/v1/users/invite",
                           headers={"Authorization": f"Bearer {atok}"},
                           json={"email": "inv2-v@test.dev", "role": "viewer", "full_name": "V"})
    itok = ri.json()["data"]["token"]
    await client.post("/api/v1/auth/register", json={
        "email": "inv2-v@test.dev", "username": "inv2v", "full_name": "V",
        "password": "Str0ng!Pass9", "invite_token": itok})
    # replay: same token — must NOT join the inviter's tenant.
    # INVITE-2 strengthened this contract: a consumed token previously
    # degraded silently into a fresh-tenant ADMIN registration (fake
    # success); now the redemption must be rejected outright (409).
    r2 = await client.post("/api/v1/auth/register", json={
        "email": "inv2-w@test.dev", "username": "inv2w", "full_name": "W",
        "password": "Str0ng!Pass9", "invite_token": itok})
    assert r2.status_code == 409, \
        f"consumed invite token must be rejected, not silently re-purposed: {r2.status_code}"


@pytest.mark.asyncio
class TestInviteTokenExhaustion:
    async def test_consumed_or_forged_invite_token_is_rejected_not_fresh_tenant(self, client, db_session):
        """INVITE-2: registering with an invite token that no longer resolves
        (consumed already / never existed) must FAIL.  Previously the branch
        silently fell through to a fresh-tenant ADMIN registration — a fake
        success: the invitee believed they joined the inviting org."""
        from sqlalchemy import text

        # real invite → mint + consume exactly once
        r = await client.post("/api/v1/auth/register", json={
            "email": "inv-x1@test.dev", "username": "invx1", "full_name": "X One",
            "password": "Str0ng!Pass9", "company_name": "OrgInvX"})
        assert r.status_code in (200, 201), r.text
        hA = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
        inv = await client.post("/api/v1/users/invite", headers=hA,
                                json={"email": "inv-x2@test.dev", "role": "viewer",
                                      "full_name": "X Two"})
        assert inv.status_code == 201, inv.text
        tok = inv.json()["data"]["token"]
        ok  = await client.post("/api/v1/auth/register", json={
            "email": "inv-x2@test.dev", "username": "invx2", "full_name": "X Two",
            "password": "Str0ng!Pass9", "invite_token": tok})
        assert ok.status_code == 200, ok.text

        # replay of the CONSUMED token (different email) must not succeed
        replay = await client.post("/api/v1/auth/register", json={
            "email": "inv-x3@test.dev", "username": "invx3", "full_name": "X Three",
            "password": "Str0ng!Pass9", "invite_token": tok})
        assert replay.status_code == 409, (
            f"consumed invite token must be rejected, got {replay.status_code}: {replay.text[:160]}")

        # a forged/unknown token must fail the same way
        forged = await client.post("/api/v1/auth/register", json={
            "email": "inv-x4@test.dev", "username": "invx4", "full_name": "X Four",
            "password": "Str0ng!Pass9", "invite_token": "forged-token-does-not-exist"})
        assert forged.status_code == 409, (
            f"unknown invite token must be rejected, got {forged.status_code}: {forged.text[:160]}")

        # sanity: neither replay nor forged registration created a tenant row
        q = await db_session.execute(text(
            "SELECT COUNT(*) FROM users WHERE email IN ('inv-x3@test.dev','inv-x4@test.dev')"))
        assert q.scalar() == 0, "rejected invite registrations must not persist users"
