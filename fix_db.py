"""Legacy one-off table-creation helper (root copy).

Sprint 4: this script is a development/test convenience.  In
``production`` / ``staging`` / ``prod`` environments it refuses to
call ``create_all`` — schema management is the responsibility of
Alembic (see ``backend/alembic/versions/``).
"""
import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import create_async_engine
from app.models.base import BaseModel
from app.models.intelligence import (
    ProviderMetadata,
    ProviderConfiguration,
    ProviderCapability,
    ProviderVersion,
    ProviderHealth,
    IntelligenceCacheEntry,
    NormalizationAudit,
    IntelligenceProvenance,
    SyncHistory,
    IntelligenceVersion,
)
from app.models.cache import SyncJob, CacheMetadata, CacheVersion


async def main():
    env = (os.environ.get("APP_ENV") or "development").lower()
    if env in {"production", "prod", "staging"}:
        print(
            f"ERROR: fix_db.py refusing to run in APP_ENV={env} — "
            "author an Alembic migration instead.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    engine = create_async_engine(
        os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://uniops:uniops_password@db:5432/uniops_db",
        )
    )
    async with engine.begin() as conn:
        # Create all intelligence tables
        await conn.run_sync(BaseModel.metadata.create_all)
        print("Tables created successfully")


if __name__ == "__main__":
    asyncio.run(main())
