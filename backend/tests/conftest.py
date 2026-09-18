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

from app.core.database import Base, get_db
import app.models as _app_models  # noqa  (module import only — must NOT shadow the FastAPI `app` name)
from app.main import app

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

# R27 (P1.6 harness hardening): file-backed SQLite with the default async
# QueuePool so every session gets its OWN connection and transaction.
# In-memory + StaticPool shared ONE connection — and therefore ONE
# physical SQLite transaction — across concurrently executing requests:
# the rollback in one request's error teardown silently discarded a
# sibling request's already-responded writes (P1.6 gate probe: concurrent
# duplicate-register returned [200, 409, 200, 409] with ZERO rows
# persisted, reproduced under CPU load).  Production runs per-request
# connections with real transaction isolation; the rig must mirror that
# or concurrent-request tests exercise impossible physics.  The
# ``reset_database`` autouse fixture still wipes + recreates the schema
# before each test, so isolation is preserved; sqlite's default 5s busy
# timeout serializes concurrent writers so the losing duplicate INSERT
# surfaces the real UNIQUE violation (409 path) instead of colliding
# inside the shared transaction.  The DB file lives in the system temp
# dir, not the repo.
import tempfile as _tempfile

_TEST_DB_PATH = _tempfile.mktemp(prefix="uniops_pytest_", suffix=".db")
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{_TEST_DB_PATH}"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
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

    Temp-file SQLite + pooled per-session connections; the schema is
    wiped and recreated before each test begins.  The fix for the legacy
    "database schema has changed" error was to recreate the schema in a
    single PRAGMA-compatible transaction.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    # Rate-limit buckets persist per-process by design (production behavior
    # must keep limits across requests); tests need per-test isolation.
    try:
        from app.core.rate_limit import _buckets
        _buckets.clear()
    except Exception:
        pass
    # Redis client singleton must not leak across tests (fakeredis instances
    # injected by one test would otherwise contaminate the next).
    try:
        import app.core.redis_client as _rc
        _rc._redis = None
    except Exception:
        pass
    # If a real Redis is reachable in the dev environment it must ALSO be
    # flushed between tests — shared counters (rate limits, invites,
    # blacklists) otherwise accumulate across the suite just like the DB.
    try:
        import redis as _sync_redis
        from app.config import get_settings
        _u = get_settings().REDIS_URL.replace("rediss://", "redis://")
        _port = 6379
        try:
            _port = int(_u.rsplit(":", 2)[1].split("/")[0])
        except Exception:
            pass
        _host = _u.split("//", 1)[1].split(":")[0]
        if _host in ("localhost", "127.0.0.1"):
            _r = _sync_redis.Redis(host=_host, port=_port, socket_timeout=1,
                                   socket_connect_timeout=1)
            _r.ping()
            _r.flushdb()
    except Exception:
        pass  # no reachable Redis — fine, memory fallbacks are per-process
    yield
    # Do NOT drop on teardown — the next test's drop_all will clean up.


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    # Mirror production get_db (commit-on-success / rollback-on-error) —
    # without the commit, persistence-dependent flows (register → login)
    # silently lose rows between requests.
    async def override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    # raise_app_exceptions=False: endpoints that intentionally translate our
    # UniOpsException subclasses (401/403/…)-into-JSON via the global handler
    # must return that response to the test client instead of re-raising, so
    # negative-path assertions (wrong password, missing token) can run.
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Session-level safety net ─────────────────────────────────────
@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_session():
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()