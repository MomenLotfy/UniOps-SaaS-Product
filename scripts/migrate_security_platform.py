#!/usr/bin/env python3
"""
Migration: Security Remediation Platform

Sprint 4: this script is a development/test convenience.  In
``production`` / ``staging`` / ``prod`` environments the script
refuses to call ``create_all`` — every schema change must flow
through Alembic (see ``backend/alembic/versions/``).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.models  # noqa: F401 — registers all models including new ones
from app.core.database import Base, engine


async def run():
    env = (os.environ.get("APP_ENV") or "development").lower()
    if env in {"production", "prod", "staging"}:
        print(
            f"ERROR: migrate_security_platform.py refusing to run in "
            f"APP_ENV={env} — author an Alembic migration instead.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print("Running Security Platform migration...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Migration complete.")
    print("Tables created/verified:")
    print("  - security_policies")
    print("  - security_exceptions")
    print("  - security_reports")
    print("  - security_posture_scores")


if __name__ == "__main__":
    asyncio.run(run())
