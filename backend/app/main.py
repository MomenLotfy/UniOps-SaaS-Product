from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.database import init_db
from app.core.security import decode_token
from app.api.v1.router import api_router
from app.api.v1.websocket.manager import ws_manager
from app.api.v1.websocket.handlers import handle_ws_message
from app.middleware.logging import LoggingMiddleware
from app.middleware.audit import AuditMiddleware
from app.utils.logger import logger

# ── Prometheus metrics (optional — enabled via ENABLE_METRICS=true) ───────────
import os as _os
_prometheus_available = False
if _os.getenv("ENABLE_METRICS", "false").lower() == "true":
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        _prometheus_available = True
    except ImportError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # 1. Init database (create tables if not exist)
    await init_db()
    logger.info("Database initialized")

    # 2. Start background scheduler (pod sync, cost sync, K8s watcher, etc.)
    try:
        from app.core.scheduler import start_scheduler
        await start_scheduler()
        logger.info("Background scheduler started")
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")

    # 3. Start ML reactive event listener (subscribes to Redis pub/sub)
    try:
        from app.services.ml_service import MLService

        _ml_listener_task = asyncio.create_task(
            MLService(None).start_event_listener(),
            name="ml-event-listener",
        )
        logger.info(
            "ML event listener task started — will retry Redis connection on failures"
        )
    except Exception as e:
        logger.warning(
            f"ML event listener not started (non-fatal): {e}"
        )

    # 4. Start Deployment Engine background worker (Epic 7)
    try:
        from app.core.deployment_engine.worker import run_deployment_worker
        asyncio.create_task(run_deployment_worker(), name="deployment-worker")
        logger.info("Deployment Engine worker started")
    except Exception as e:
        logger.warning(f"Deployment Engine worker not started (non-fatal): {e}")

    # 3. Register Celery webhook routes if available
    try:
        from app.api.webhooks import github as github_wh, stripe as stripe_wh
        from app.api.webhooks import gitlab as gitlab_wh, slack as slack_wh
        app.include_router(github_wh.router, prefix="/webhooks", tags=["Webhooks-Inbound"])
        app.include_router(stripe_wh.router, prefix="/webhooks", tags=["Webhooks-Inbound"])
        app.include_router(gitlab_wh.router, prefix="/webhooks", tags=["Webhooks-Inbound"])
        app.include_router(slack_wh.router,  prefix="/webhooks", tags=["Webhooks-Inbound"])
    except Exception as e:
        logger.warning(f"Webhook routes not loaded: {e}")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down...")
    try:
        from app.core.scheduler import stop_scheduler
        await stop_scheduler()
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    description="UniOps Control Tower — Backend API",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Expose /metrics endpoint for Prometheus scraping
if _prometheus_available:
    Instrumentator(
        should_group_status_codes=True,
        excluded_handlers=["/health", "/metrics"],
    ).instrument(app).expose(app)
    logger.info("Prometheus metrics enabled at /metrics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuditMiddleware)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str, token: str = ""):
    try:
        if token:
            decode_token(token)
    except Exception:
        await websocket.close(code=4001)
        return
    await ws_manager.connect(websocket, tenant_id)
    try:
        while True:
            data = await websocket.receive_text()
            await handle_ws_message(websocket, tenant_id, data)
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, tenant_id)


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    from app.core.scheduler import _scheduler
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
        "websocket_connections": ws_manager.total_connections,
        "scheduler_tasks": len(_scheduler._tasks),
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    from app.core.exceptions import UniOpsException
    if isinstance(exc, UniOpsException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.message, "code": exc.code},
        )
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error", "code": "INTERNAL_ERROR"},
    )
