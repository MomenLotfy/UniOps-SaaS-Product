#!/bin/sh
set -e

echo "================================================"
echo " UniOps backend starting"
echo " DATABASE_URL = $DATABASE_URL"
echo " REDIS_URL    = $REDIS_URL"
echo "================================================"

# Ensure beat schedule directory exists (celery_beat uses it)
mkdir -p /app/beat

# ── Step 1: Wait for PostgreSQL ──────────────────────────────────────────────
echo "[1/4] Waiting for database..."
RETRIES=30
until python -c "
import sys, os, asyncio, asyncpg
async def chk():
    url = os.environ.get('DATABASE_URL', '').replace('postgresql+asyncpg://', 'postgresql://')
    if not url or url.startswith('sqlite'):
        sys.exit(0)  # SQLite — no wait needed
    conn = await asyncpg.connect(url)
    await conn.close()
asyncio.run(chk())
" 2>/dev/null; do
    RETRIES=$((RETRIES - 1))
    if [ $RETRIES -le 0 ]; then
        echo "ERROR: database never became available — check DATABASE_URL and db service"
        exit 1
    fi
    echo "  postgres not ready ($RETRIES retries left)..."
    sleep 2
done
echo "  ✓ database ready"

# ── Step 2: Wait for Redis ───────────────────────────────────────────────────
echo "[2/4] Waiting for Redis..."
REDIS_RETRIES=20
REDIS_HOST=$(echo "${REDIS_URL:-redis://redis:6379/0}" | sed 's|redis://||' | cut -d: -f1)
REDIS_PORT=$(echo "${REDIS_URL:-redis://redis:6379/0}" | sed 's|redis://||' | cut -d: -f2 | cut -d/ -f1)
until python -c "
import socket, sys
h, p = '${REDIS_HOST}', int('${REDIS_PORT}')
try:
    s = socket.create_connection((h, p), timeout=3)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    REDIS_RETRIES=$((REDIS_RETRIES - 1))
    if [ $REDIS_RETRIES -le 0 ]; then
        echo "  ⚠ Redis not reachable — continuing without it (Celery tasks will queue)"
        break
    fi
    echo "  redis not ready ($REDIS_RETRIES retries left)..."
    sleep 2
done
echo "  ✓ Redis check complete"

# ── Step 3: Run database migrations ─────────────────────────────────────────
# Sprint 4: in production we rely on Alembic exclusively.  The
# create_all fallback would silently shadow the migration chain and
# is permitted only in non-production environments (APP_ENV ∈
# {development, test, dev}).  In production a failed migration is
# fatal — the operator must fix the migration or restore a backup
# before the API can boot.
echo "[3/4] Running alembic migrations..."
APP_ENV_LC=$(echo "${APP_ENV:-development}" | tr '[:upper:]' '[:lower:]')
if ! alembic upgrade head 2>&1; then
    if [ "$APP_ENV_LC" = "production" ] || [ "$APP_ENV_LC" = "prod" ] || [ "$APP_ENV_LC" = "staging" ]; then
        echo "  ✗ alembic migration failed in $APP_ENV_LC — refusing to start"
        echo "    (create_all fallback is disabled in production; restore DB or fix migration)"
        exit 1
    fi
    echo "  ⚠ alembic migration failed in $APP_ENV_LC — falling back to SQLAlchemy create_all"
    python -c "
import asyncio, sys
sys.path.insert(0, '/app')
async def create_tables():
    from app.core.database import engine, Base
    import app.models  # noqa: registers all models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('  Tables created via SQLAlchemy fallback')
asyncio.run(create_tables())
" || echo "  ⚠ table creation fallback also failed — continuing anyway"
fi
echo "  ✓ migrations complete"

# ── Step 4: Seed demo data ───────────────────────────────────────────────────
echo "[4/4] Seeding demo data..."
python scripts/seed_data.py || echo "  ⚠ seed_data.py failed (non-fatal — data may already exist)"
echo "  ✓ seed complete"

echo "================================================"
echo " Starting uvicorn on 0.0.0.0:8000"
echo "================================================"
exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --log-level info \
    --no-access-log
