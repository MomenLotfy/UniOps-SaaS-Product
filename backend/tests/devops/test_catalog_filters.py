"""
BUG-013 — catalog listing must report a `total` that honours the same filters
as `data`.

The old code built the page query with status/type/search conditions but built
the count query from `tenant_id` alone, so `total` described the unfiltered
catalog while `data` described the filtered one. Pagination was therefore
wrong: the client was told there were more pages than the filtered set has.

These are real HTTP round-trips against the ASGI app with a seeded tenant.
"""
from __future__ import annotations

import jwt as pyjwt
import pytest

from app.models.service import CatalogService


async def _register(client, email: str, org: str):
    username = email.split("@")[0].replace("-", "_")
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "full_name": "Admin",
        "password": "Str0ng!Pass9", "company_name": org,
    })
    assert r.status_code in (200, 201), r.text
    tok = r.json()["data"]["access_token"]
    claims = pyjwt.decode(tok, options={"verify_signature": False})
    return {"Authorization": f"Bearer {tok}"}, claims["tenant_id"]


async def _seed_catalog(db, tenant_id: str):
    """3 Running microservices + 1 Failed database + 1 Running gateway."""
    rows = [
        ("api-one",   "Running", "Microservice", "Python"),
        ("api-two",   "Running", "Microservice", "Go"),
        ("api-three", "Running", "Microservice", "Rust"),
        ("primary-db", "Failed", "Database",     "Postgres"),
        ("edge-gw",   "Running", "Gateway",      "Envoy"),
    ]
    for name, status, stype, stack in rows:
        db.add(CatalogService(
            tenant_id=tenant_id, name=name, type=stype,
            tech_stack=stack, status=status,
        ))
    await db.commit()


@pytest.fixture
async def catalog_env(client, db_session):
    headers, tenant_id = await _register(client, "catalog-t@test.dev", "OrgCatalog")
    await _seed_catalog(db_session, tenant_id)
    return client, headers, tenant_id


@pytest.mark.asyncio
async def test_unfiltered_total_matches_full_catalog(catalog_env):
    client, headers, _ = catalog_env
    r = await client.get("/api/v1/catalog/services", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 5
    assert len(body["data"]) == 5


@pytest.mark.asyncio
async def test_status_filter_total_honours_the_filter(catalog_env):
    """The core BUG-013 assertion: filtered page and filtered total agree."""
    client, headers, _ = catalog_env

    r = await client.get("/api/v1/catalog/services?status=Running", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert len(body["data"]) == 4
    # Before the fix this reported 5 (the unfiltered tenant count).
    assert body["total"] == 4
    assert all(s["status"] == "Running" for s in body["data"])


@pytest.mark.asyncio
async def test_type_filter_total_honours_the_filter(catalog_env):
    client, headers, _ = catalog_env

    r = await client.get("/api/v1/catalog/services?type=Database", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert len(body["data"]) == 1
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_search_filter_total_honours_the_filter(catalog_env):
    client, headers, _ = catalog_env

    r = await client.get("/api/v1/catalog/services?search=api-", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert len(body["data"]) == 3
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_combined_filters_narrow_total(catalog_env):
    client, headers, _ = catalog_env

    r = await client.get(
        "/api/v1/catalog/services?status=Running&type=Microservice", headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert len(body["data"]) == 3
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_pagination_reports_no_phantom_pages(catalog_env):
    """
    The user-visible symptom: with page_size=2 and a filter matching 4 rows,
    the old code reported total=5 and so implied 3 pages where only 2 exist.
    """
    client, headers, _ = catalog_env

    r = await client.get(
        "/api/v1/catalog/services?status=Running&page=1&page_size=2", headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert len(body["data"]) == 2
    assert body["total"] == 4                      # not 5
    assert body["page"] == 1
    assert body["page_size"] == 2

    # A page beyond the filtered set must come back empty, not phantom rows.
    r3 = await client.get(
        "/api/v1/catalog/services?status=Running&page=3&page_size=2", headers=headers
    )
    assert r3.status_code == 200, r3.text
    assert r3.json()["data"] == []


@pytest.mark.asyncio
async def test_filter_matching_nothing_returns_zero_total(catalog_env):
    client, headers, _ = catalog_env

    r = await client.get("/api/v1/catalog/services?status=Stopped", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["data"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_total_never_leaks_another_tenants_count(catalog_env):
    """Tenant isolation must survive the shared-conditions refactor."""
    client, headers, _ = catalog_env
    other_headers, _ = await _register(client, "catalog-u@test.dev", "OrgCatalogOther")

    r = await client.get("/api/v1/catalog/services", headers=other_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["total"] == 0
    assert body["data"] == []
