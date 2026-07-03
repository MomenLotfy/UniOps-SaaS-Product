import asyncio
from logging.config import fileConfig
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine
from alembic import context
import sqlalchemy as sa

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.config import settings
from app.core.database import Base
import app.models  # noqa: F401

target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _ensure_version_col_wide_enough(engine) -> None:
    """
    alembic hardcodes version_num as VARCHAR(32). Several revision IDs in this
    project exceed 32 chars. Widen the column before migrations run so the
    INSERT/UPDATE doesn't fail with StringDataRightTruncationError.
    Runs in its own autocommit connection so it doesn't pollute the migration tx.
    """
    async with engine.connect() as conn:
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(255) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        ))
        await conn.commit()
        # Widen existing column if it was already created with VARCHAR(32)
        try:
            await conn.execute(text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(255)"
            ))
            await conn.commit()
        except Exception:
            await conn.rollback()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    await _ensure_version_col_wide_enough(connectable)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
