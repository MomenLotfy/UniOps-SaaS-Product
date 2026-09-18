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
    # replay: same token — second registrant must NOT join the inviter's tenant
    r2 = await client.post("/api/v1/auth/register", json={
        "email": "inv2-w@test.dev", "username": "inv2w", "full_name": "W",
        "password": "Str0ng!Pass9", "invite_token": itok})
    assert r2.status_code in (200, 201)
    wclaims = jwt.decode(r2.json()["data"]["access_token"], options={"verify_signature": False})
    aclaims = jwt.decode(atok, options={"verify_signature": False})
    assert wclaims["tenant_id"] != aclaims["tenant_id"], "consumed invite must not bind again"
