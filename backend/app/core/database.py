from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    poolclass=NullPool,
)

_celery_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
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

CelerySessionLocal = async_sessionmaker(
    _celery_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
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
    """
    Import model modules so Alembic / test discovery sees every
    declarative class.

    Sprint 4: production startup relies exclusively on Alembic
    migrations (see ``alembic upgrade head`` in entrypoint.sh).
    ``Base.metadata.create_all`` is a development convenience that
    must never run in production — it would create tables that Alembic
    has not yet stamped, breaking the migration chain.  The function
    therefore is a no-op when ``APP_ENV`` is ``production`` /
    ``staging`` / ``prod``.
    """
    import logging

    import app.models  # noqa: F401
    env = (settings.APP_ENV or "").lower()
    if env in {"production", "prod", "staging"}:
        logging.getLogger(__name__).info(
            "init_db skipped (APP_ENV=%s) — Alembic is the source of truth", env
        )
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
