#!/usr/bin/env python3
"""Create a new tenant (organization) in UniOps with an admin user.

Usage:
    python scripts/create_tenant.py --name "Acme Corp" --slug acme --email admin@acme.com
"""
import asyncio
import argparse
import secrets
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def create_tenant(name: str, slug: str, email: str, full_name: str, plan: str = "free") -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.core.security import hash_password
    from sqlalchemy import select

    password = secrets.token_urlsafe(16)

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(Tenant).where(Tenant.slug == slug))
        if existing.scalar_one_or_none():
            print(f"ERROR: Tenant with slug '{slug}' already exists", file=sys.stderr)
            sys.exit(1)

        tenant = Tenant(name=name, slug=slug, plan=plan, is_active=True)
        db.add(tenant)
        await db.flush()

        username = f"{slug}_admin"
        user = User(
            tenant_id=tenant.id,
            email=email,
            username=username,
            full_name=full_name,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(user)

    print(f"\n{'=' * 50}")
    print(f"Tenant Created Successfully!")
    print(f"{'=' * 50}")
    print(f"  Tenant ID:   {tenant.id}")
    print(f"  Name:        {tenant.name}")
    print(f"  Slug:        {tenant.slug}")
    print(f"  Plan:        {tenant.plan}")
    print(f"\n  Admin User:")
    print(f"  User ID:     {user.id}")
    print(f"  Email:       {user.email}")
    print(f"  Username:    {user.username}")
    print(f"  Password:    {password}  ← SAVE THIS NOW")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create UniOps Tenant")
    parser.add_argument("--name", required=True, help="Organization name")
    parser.add_argument("--slug", required=True, help="URL-friendly slug (unique)")
    parser.add_argument("--email", required=True, help="Admin user email")
    parser.add_argument("--full-name", default="Admin User", help="Admin user full name")
    parser.add_argument("--plan", default="free", choices=["free", "starter", "professional", "enterprise"])
    args = parser.parse_args()

    asyncio.run(create_tenant(args.name, args.slug, args.email, args.full_name, args.plan))
