"""Initialize database and create tables.

Sprint 4: this script is a development/test convenience.  In
``production`` / ``staging`` / ``prod`` environments the script
refuses to call ``create_all`` — Alembic is the only legitimate
source of schema changes in those environments.
"""
import asyncio
import os
import sys

import app.models  # noqa: F401 - import all models to register them
from app.core.database import Base, engine


async def init_db():
    env = (os.environ.get("APP_ENV") or "development").lower()
    if env in {"production", "prod", "staging"}:
        print(
            f"ERROR: init_db.py refusing to run in APP_ENV={env} — "
            "use `alembic upgrade head` instead.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
