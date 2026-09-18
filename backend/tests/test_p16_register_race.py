"""P1.6-RACE-1 — concurrent same-user registration must never 500.

Pre-fix (live logs): concurrent same-username registrations raced on
tenants.slug (check-then-insert) and the loser surfaced an unhandled
IntegrityError → 500.  Post-fix: truthful distribution (one 200, rest
409-conflict and/or 429-rate-limit), never a server error.
"""
import asyncio

import pytest


@pytest.mark.asyncio
async def test_concurrent_registration_never_500s(client):
    payload = {"email": "race-t@test.dev", "username": "racetest", "full_name": "R",
               "password": "Str0ng!Pass9", "company_name": "OrgRace"}
    results = await asyncio.gather(*[
        client.post("/api/v1/auth/register", json=payload) for _ in range(6)
    ])
    codes = sorted(r.status_code for r in results)
    assert not any(c >= 500 for c in codes), f"race leaked server errors: {codes}"
    # exactly one winner; losers are truthful (409 conflict / 429 rate-limit)
    assert codes.count(200) == 1 or codes.count(201) == 1, codes
    assert all(c in (200, 201, 409, 429) for c in codes), codes
