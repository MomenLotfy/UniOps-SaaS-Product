import asyncio
from app.core.database import AsyncSessionLocal
from app.models.scan import Repository
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Repository))
        repos = res.scalars().all()
        print(f"Total repos: {len(repos)}")
        for r in repos[:5]:
            print(f"- {r.name} (integration={r.integration_id})")

if __name__ == "__main__":
    asyncio.run(main())
