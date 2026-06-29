"""
Sprint 1 R7: tests must run with a valid SECRET_KEY — otherwise
`Settings()` instantiation will refuse to boot (R7 hardening).

Sprint 2 R25: full DB reset between tests — every test gets a clean
schema state via per-test DROP_ALL + CREATE_ALL.
"""
import os
os.environ.setdefault(
    "SECRET_KEY",
    "uniops-e2e-fixture-secret-please-replace-in-production-env-0001",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "uniops-e2e-fixture-jwt-secret-please-replace-in-production-env-001",
)
os.environ.setdefault("APP_ENV", "test")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
import app.models  # noqa

# Register all security submodule models so SQLAlchemy can resolve FKs
# and so `Base.metadata.create_all` produces the full schema.
# Importing the *models package* ensures every concrete model class is
# loaded and registered with `Base.metadata`.
from app.modules.security.decision_engine.models import (  # noqa: F401
    decision as _de_decision,
    plan as _de_plan,
    context as _de_context,
    evidence as _de_evidence,
    policy as _de_policy,
    statistics as _de_statistics,
)
from app.modules.security.decision_strategy.models import strategy as _ds_strategy  # noqa: F401
from app.modules.security.decision_approval.models import approval as _da_approval  # noqa: F401
from app.modules.security.execution_orchestration.models import execution as _eo_execution  # noqa: F401

# R27: in-memory SQLite + StaticPool.  StaticPool reuses a single
# connection across every test, so the in-memory schema created by the
# first ``create_all`` is visible to every subsequent session.  The
# ``reset_database`` autouse fixture wipes + recreates the schema
# before each test, so isolation is preserved.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_database():
    """
    R25 — full DB reset between tests.

    Strategy: drop_all + create_all on every test start.  This is the
    strictest isolation possible — no row from a previous test can leak
    into the next.

    In-memory SQLite + StaticPool shares one connection across all
    tests; the schema is wiped and recreated before each test begins.
    The fix for the legacy "database schema has changed" error was to
    recreate the schema in a single PRAGMA-compatible transaction.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Do NOT drop on teardown — the next test's drop_all will clean up.


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Session-level safety net ─────────────────────────────────────
@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_session():
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()