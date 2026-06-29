"""
Health API — liveness, readiness, startup, and system status.

Sprint 3 R38 split the previous single ``GET /`` into three probes
that the orchestrator can call independently:

  - ``GET /``           — summary, returns version + env (always 200).
  - ``GET /live``       — liveness, always 200 unless the process is
                         wedged (does no I/O).
  - ``GET /ready``      — readiness: DB + Redis + scheduler + event bus.
                         Returns 503 if any critical dep is down.
  - ``GET /startup``    — startup: only 200 once lifespan startup has
                         fully completed.  Until then 503.

The /metrics endpoint is preserved for backward compatibility (returns
``websocket_connections`` etc.).
"""
from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.config import settings
from app.observability.startup_validator import StartupReport
from app.utils.logger import logger

router = APIRouter()


# ── Startup flag (set by lifespan when fully ready) ──────────────────────────
_startup_complete: bool = False
_startup_report: StartupReport | None = None


def mark_startup_complete(report: StartupReport | None = None) -> None:
    """Called from the FastAPI lifespan once every init step finished."""
    global _startup_complete, _startup_report
    _startup_complete = True
    _startup_report = report


def is_startup_complete() -> bool:
    return _startup_complete


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.get("")
async def health_check():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
    }


@router.get("/live")
async def liveness_check():
    """Liveness — must NEVER depend on external services."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness_check(response: Response):
    """Readiness — checks DB, Redis, scheduler.  503 on critical failure."""
    checks: dict = {}

    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:  # pragma: no cover - I/O
        checks["database"] = f"error: {e}"

    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:  # pragma: no cover - I/O
        checks["redis"] = f"error: {e}"

    try:
        from app.core.scheduler import _scheduler
        checks["scheduler"] = (
            "ok" if _scheduler is not None and getattr(_scheduler, "running", False) else "not_running"
        )
    except Exception:  # pragma: no cover - defensive
        checks["scheduler"] = "unavailable"

    critical_failed = any(
        v != "ok" for k, v in checks.items() if k in {"database", "redis"}
    )
    if critical_failed:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "degraded",
            "checks": checks,
            "version": settings.APP_VERSION,
        }
    return {
        "status": "ready",
        "checks": checks,
        "version": settings.APP_VERSION,
    }


@router.get("/startup")
async def startup_check(response: Response):
    """Startup probe — 200 only after lifespan has completed."""
    if not _startup_complete:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "starting",
            "version": settings.APP_VERSION,
            "report": _startup_report.__dict__ if _startup_report else None,
        }
    return {
        "status": "started",
        "version": settings.APP_VERSION,
        "report": _startup_report.__dict__ if _startup_report else None,
    }


@router.get("/metrics")
async def get_metrics():
    try:
        from app.api.v1.websocket.manager import ws_manager
        ws_connections = ws_manager.total_connections
    except Exception:  # pragma: no cover - defensive
        ws_connections = 0
    return {
        "websocket_connections": ws_connections,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


__all__ = [
    "router",
    "mark_startup_complete",
    "is_startup_complete",
]
