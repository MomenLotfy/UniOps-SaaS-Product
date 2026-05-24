from __future__ import annotations
"""Health API — liveness, readiness, and system status."""
from fastapi import APIRouter
from app.schemas.common import APIResponse
from app.config import settings
from app.utils.logger import logger

router = APIRouter()


@router.get("")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION, "env": settings.APP_ENV}


@router.get("/ready")
async def readiness_check():
    checks = {}

    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "version": settings.APP_VERSION,
    }


@router.get("/metrics")
async def get_metrics():
    try:
        from app.api.v1.websocket.manager import ws_manager
        ws_connections = ws_manager.total_connections
    except Exception:
        ws_connections = 0
    return {
        "websocket_connections": ws_connections,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }
