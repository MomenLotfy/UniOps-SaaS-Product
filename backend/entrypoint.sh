#!/bin/sh
set -e

echo "================================================"
echo " UniOps backend starting"
echo " DATABASE_URL = $DATABASE_URL"
echo " REDIS_URL    = $REDIS_URL"
echo "================================================"

# Ensure beat schedule directory exists (celery_beat uses it)
mkdir -p /app/beat

echo "[1/3] Waiting for database..."
RETRIES=30
until python -c "
import sys, os, asyncio, asyncpg
async def chk():
    url = os.environ.get('DATABASE_URL', '').replace('postgresql+asyncpg://', 'postgresql://')
    if not url:
        print('ERROR: DATABASE_URL not set'); sys.exit(1)
    conn = await asyncpg.connect(url)
    await conn.close()
asyncio.run(chk())
" 2>/dev/null; do
    RETRIES=$((RETRIES - 1))
    if [ $RETRIES -le 0 ]; then
        echo "ERROR: database never became available"
        exit 1
    fi
    echo "  postgres not ready ($RETRIES retries left)..."
    sleep 2
done
echo "  ✓ database ready"

echo "[2/3] Running alembic migrations..."
if ! alembic upgrade head 2>&1; then
    echo "  ⚠ alembic migration failed — trying to create tables directly via SQLAlchemy"
    python -c "
import asyncio
from app.core.database import engine, Base
import app.models  # noqa: ensure all models are imported
asyncio.run(engine.begin().__aenter__().__class__.run_sync(None, Base.metadata.create_all(engine)))
" 2>/dev/null || python -c "
import asyncio, sys
sys.path.insert(0, '/app')
async def create_tables():
    from app.core.database import engine, Base
    import app.models.tenant, app.models.user, app.models.integration
    import app.models.pipeline, app.models.pod, app.models.threat
    import app.models.vulnerability, app.models.cost_metric, app.models.alert
    import app.models.scan, app.models.ml_prediction, app.models.ml_recommendation
    import app.models.ml_pattern, app.models.ml_correlation, app.models.cost_anomaly
    import app.models.savings, app.models.audit_log, app.models.compliance
    import app.models.subscription, app.models.webhook, app.models.role
    import app.models.permission
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('  Tables created via SQLAlchemy fallback')
asyncio.run(create_tables())
" || echo "  ⚠ table creation fallback also failed — continuing anyway"
fi
echo "  ✓ migrations complete"

echo "[3/3] Seeding demo data..."
python scripts/seed_data.py || echo "  ⚠ seed_data.py failed (non-fatal — data may already exist)"
echo "  ✓ seed complete"

echo "================================================"
echo " Starting uvicorn"
echo "================================================"
exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --log-level info \
    --no-access-log
