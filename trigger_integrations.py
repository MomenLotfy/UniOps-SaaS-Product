import asyncio
from app.core.database import AsyncSessionLocal
from app.models.integration import Integration
from app.services.integration_service import IntegrationService
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        svc = IntegrationService(db)
        query = select(Integration).where(Integration.is_active == True)
        result = await db.execute(query)
        integrations = result.scalars().all()
        print(f"Found {len(integrations)} active integrations")
        
        for intg in integrations:
            print(f"Testing {intg.type} integration {intg.id} (current status: {intg.status})...")
            try:
                res = await svc.test_connection(str(intg.id))
                await db.commit()
                print(f"  Result: success={res.success}, message={res.message}")
                if res.success:
                    print(f"  Triggering sync for {intg.id}...")
                    await svc.sync(str(intg.id))
                    await db.commit()
                    print(f"  Sync triggered.")
            except Exception as e:
                print(f"  Error testing {intg.id}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
