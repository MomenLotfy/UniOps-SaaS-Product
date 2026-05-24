#!/usr/bin/env python3
"""Create a super admin user with cross-tenant access.

Usage:
    python scripts/create_superadmin.py --email admin@uniops.io --name "Super Admin"
"""
import asyncio
import argparse
import secrets
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def create_superadmin(email: str, full_name: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.core.security import hash_password
    from sqlalchemy import select

    password = secrets.token_urlsafe(20)

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"ERROR: User with email '{email}' already exists", file=sys.stderr)
            sys.exit(1)

        sys_tenant = await db.execute(select(Tenant).where(Tenant.slug == "system"))
        tenant = sys_tenant.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(name="UniOps System", slug="system", plan="enterprise", is_active=True)
            db.add(tenant)
            await db.flush()

        username = email.split("@")[0] + "_superadmin"
        user = User(
            tenant_id=tenant.id,
            email=email,
            username=username,
            full_name=full_name,
            hashed_password=hash_password(password),
            role="super_admin",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    print(f"\n{'=' * 55}")
    print("Super Admin Created!")
    print(f"{'=' * 55}")
    print(f"  User ID:   {user.id}")
    print(f"  Email:     {user.email}")
    print(f"  Role:      {user.role}")
    print(f"  Password:  {password}  ← STORE SECURELY")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create UniOps Super Admin")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Super Admin")
    args = parser.parse_args()
    asyncio.run(create_superadmin(args.email, args.name))
