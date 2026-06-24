#!/usr/bin/env python3
"""
Migration: Security Remediation Platform
Creates new tables: security_policies, security_exceptions,
security_reports, security_posture_scores.
Safe to run multiple times (CREATE TABLE IF NOT EXISTS).
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import engine, Base
import app.models  # noqa: F401 — registers all models including new ones


async def run():
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
