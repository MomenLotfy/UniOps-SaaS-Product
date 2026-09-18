"""P1.6-INTEL-1 — feed-sync endpoint must never fabricate success.

Pre-fix: POST /intelligence/feeds/{provider_id}/sync returned
{"success": true, "Sync triggered"} with NO dispatch.  Post-fix: 503 honest
for existing providers (no sync pipeline configured), 404 for unknown.
"""
import pytest
import jwt
from sqlalchemy import text
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_existing_provider_gets_honest_503(client, db_session):
    r = await client.post("/api/v1/auth/register", json={
        "email": "int-a@test.dev", "username": "inta", "full_name": "A",
        "password": "Str0ng!Pass9", "company_name": "OrgInt"})
    tok = r.json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    now = datetime.now(timezone.utc).isoformat()
    await db_session.execute(text(
        "DELETE FROM intelligence_provider_metadata WHERE provider_id='p16-prov'"))
    # table name may differ; discover it
    names = await db_session.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%provider%'"))
    tbl = [n[0] for n in names]
    assert tbl, "provider metadata table missing"
    t = tbl[0]
    await db_session.execute(text(
        f"INSERT INTO {t} (id, provider_id, name, version, is_active, refresh_interval_seconds, created_at, updated_at) "
        f"VALUES ('row-p16','p16-prov','P16 Provider','1.0',1,86400,:n,:n)"), {"n": now})
    await db_session.commit()

    r = await client.post("/api/v1/intelligence/feeds/p16-prov/sync", headers=h)
    assert r.status_code == 503, f"fake-success path must be unreachable: {r.status_code}"
    assert "success\": true" not in r.text.replace("'", '"'), "fabricated success leaked back"


@pytest.mark.asyncio
async def test_unknown_provider_still_404(client, db_session):
    r = await client.post("/api/v1/auth/register", json={
        "email": "int-b@test.dev", "username": "intb", "full_name": "A",
        "password": "Str0ng!Pass9", "company_name": "OrgInt2"})
    h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
    r = await client.post("/api/v1/intelligence/feeds/definitely-missing/sync", headers=h)
    assert r.status_code == 404
