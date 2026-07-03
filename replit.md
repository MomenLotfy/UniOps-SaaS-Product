# UniOps Control Tower

A multi-tenant DevSecOps SaaS platform unifying DevOps, Security, FinOps, and AI insights into a single intelligent control plane.

## Architecture

- **Frontend**: React + Vite + TailwindCSS in `artifacts/uniops/`, served on port 5000
- **Backend**: FastAPI + Uvicorn in `backend/`, served on port 3001
- **Database**: Replit PostgreSQL (`postgresql+asyncpg://postgres:password@helium/heliumdb?sslmode=disable`)
- **Queue**: Redis (port 6379) + Celery worker + Celery beat
- **Python**: 3.11 via Nix, packages in `backend/venv/` managed with `uv`

## Workflows

| Name | Command |
|------|---------|
| Backend API | `cd backend && venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 3001` |
| Start application | `PORT=5000 pnpm --filter @workspace/uniops run dev` |
| Redis Server | `redis-server --port 6379 --loglevel notice` |
| Celery Worker | `cd backend && until redis-cli -p 6379 ping ...; do sleep 2; done && venv/bin/celery -A app.core.celery_app worker --loglevel=info -c 2` |
| Celery Beat | `cd backend && until redis-cli -p 6379 ping ...; do sleep 2; done && venv/bin/celery -A app.core.celery_app beat --loglevel=info` |

## Database Migrations

Run with: `cd backend && venv/bin/alembic upgrade head`

15 migrations (001–015) plus bridge migration `009a_decision_engine_core_tables`. The bridge creates 22 decision-engine tables that migrations 010–014 depend on via FK constraints.

**Key quirks**:
- `alembic_version.version_num` is widened to VARCHAR(255) via `_ensure_version_col_wide_enough()` in `env.py` — revision IDs exceed the default VARCHAR(32) limit.
- asyncpg doesn't support `DO $$ ... $$` blocks or `UPPER()` on enum columns; all raw DDL avoids these patterns.
- Decision-engine enums (`decisionstate`, `policystatus`, `ruleoperator`, `rulelogic`) are created using same-object-instance pattern from migration 010.

## Key Modules

- `backend/app/modules/security/decision_engine/` — 22-table decision engine
- `backend/app/api/v1/endpoints/security_exceptions.py` — Exceptions CRUD + review + revoke
- `backend/app/services/security_exception_service.py` — Service with search/filter/category/severity/revoke
- `artifacts/uniops/src/pages/SecurityCenter/sections/Exceptions.tsx` — Exceptions UI with polling, export, revoke

## User Preferences

- No mock data anywhere — all features must be backed by real API calls
- No architectural changes without explicit instruction
- All asyncpg-related DDL must avoid prepared-statement-incompatible patterns (no `DO $$`, no `UPPER()` on enums, no `checkfirst=True` enum.create via asyncpg connections)
