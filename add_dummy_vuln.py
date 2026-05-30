
import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.vulnerability import Vulnerability
from app.models.tenant import Tenant

async def add_dummy_vuln():
    async with AsyncSessionLocal() as db:
        # Get first tenant
        tenant = (await db.execute(select(Tenant))).scalars().first()
        if not tenant:
            print("No tenant found")
            return
        
        tenant_id = tenant.id
        
        vuln = Vulnerability(
            tenant_id=tenant_id,
            cve_id="CVE-2024-DUMMY",
            title="Dummy Vulnerability for Testing",
            description="This is a test vulnerability to verify the UI tab.",
            severity="high",
            status="open",
            package_name="dummy-pkg",
            package_version="1.0.0",
            target="test-repo",
            references=["http://example.com"]
        )
        db.add(vuln)
        await db.commit()
        print(f"Added dummy vulnerability to tenant {tenant_id}")

if __name__ == "__main__":
    asyncio.run(add_dummy_vuln())
