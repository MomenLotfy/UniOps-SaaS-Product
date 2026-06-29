"""Legacy one-off table-creation helper.

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


async def main():
    env = (os.environ.get("APP_ENV") or "development").lower()
    if env in {"production", "prod", "staging"}:
        print(
            f"ERROR: fix_db.py refusing to run in APP_ENV={env} — "
            "author an Alembic migration instead.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
        print("Intelligence tables created successfully")


if __name__ == "__main__":
    asyncio.run(main())
