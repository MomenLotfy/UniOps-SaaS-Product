---
name: Alembic migration quirks
description: asyncpg-specific DDL restrictions, alembic_version column width issue, and bridge migration pattern for missing FK targets.
---

## asyncpg incompatibilities

asyncpg uses prepared statements for all queries, which breaks several DDL patterns:

- **`DO $$ ... $$` blocks** — `$` is treated as a parameter placeholder. Never use dollar-quoted blocks in migrations.
- **`UPPER()` on enum columns** — PostgreSQL won't implicitly cast enum to text for string functions. Cast explicitly: `UPPER(state::text)`.
- **`sa.Enum.create(bind, checkfirst=True)`** — can false-positive on existence check. Use same-object-instance pattern (pass the same `sa.Enum` object to both `create()` and column definitions — see migration 010 for the pattern).
- **`server_default="'DRAFT'"` on enum columns** — produces triple-quoted SQL `DEFAULT '''DRAFT'''` which is invalid. Remove server_default from enum columns; handle defaults in the Python model layer.

## alembic_version VARCHAR(32) limit

The default `alembic_version.version_num` column is VARCHAR(32). Several revision IDs in this project exceed 32 chars (e.g. `012_execution_orchestration_tables` = 34). Fix: `_ensure_version_col_wide_enough()` in `backend/alembic/env.py` widens the column to VARCHAR(255) in a separate autocommit connection before migrations run.

**Why:** alembic 1.13.1 hardcodes `String(32)` in the migration module source; there's no configure() parameter to override it cleanly. The pre-migration ALTER TABLE approach is the practical workaround.

## Bridge migration pattern

When existing migrations reference FK targets that were never created (tables defined in ORM models not imported by alembic), write a bridge migration that:
1. Has `down_revision` pointing to the last successfully applied migration
2. Creates all missing tables
3. Update the next migration's `down_revision` to point to the bridge

Example: `009a_decision_engine_core_tables.py` bridges 009 → 010 by creating 22 decision-engine tables.

**How to apply:** If `alembic upgrade head` fails with `ForeignKeyViolation` or `UndefinedTable` referencing tables that aren't in any migration, check `backend/app/modules/` for ORM models not imported in `alembic/env.py`.
