import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from app.models.base import BaseModel

async def main():
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
