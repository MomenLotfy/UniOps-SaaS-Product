"""Initialize database and create tables."""
import asyncio
from app.core.database import engine, Base
import app.models  # noqa: F401 - import all models to register them


async def init_db():
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
