from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from app.config import settings

# SQLite needs different pool settings than PostgreSQL
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ── Celery / asyncio.run() session factory ────────────────────────────────────
# Celery tasks call asyncio.run() which creates a fresh event loop per task.
# asyncpg connections are event-loop bound, so reusing the pooled engine across
# different event loops raises "Future attached to a different loop".
# NullPool avoids connection reuse entirely — each task gets fresh connections.
_celery_engine = create_async_engine(
    poolclass=NullPool,
    settings.DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool,
)

CelerySessionLocal = async_sessionmaker(
    _celery_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    # Import all models so their metadata is registered before create_all
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
