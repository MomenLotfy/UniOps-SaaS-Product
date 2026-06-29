from __future__ import annotations
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import settings
from app.core.database import init_db, engine
from app.core.security import decode_token
from app.api.v1.router import api_router
from app.api.v1.websocket.manager import ws_manager
from app.api.v1.websocket.handlers import handle_ws_message
from app.middleware.logging import LoggingMiddleware
from app.middleware.audit import AuditMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.utils.logger import logger


# ── Sprint 3 observability: import lazily so missing optional deps
# (Sentry / OpenTelemetry) only log a warning instead of crashing.
def _init_observability() -> None:
    """Configure structured logging, tracing, and error capture."""
    # 1. Structured logging (structlog → loguru fallback)
    try:
        from app.observability.logging import configure_structlog
        configure_structlog(force=True)
    except Exception:
        logger.exception("configure_structlog failed (non-fatal)")

    # 2. OpenTelemetry tracing
    try:
        from app.observability.tracing import init_tracing
        init_tracing(
            service_name=settings.APP_NAME,
            service_version=settings.APP_VERSION,
            environment=settings.APP_ENV,
        )
    except Exception:
        logger.exception("init_tracing failed (non-fatal)")

    # 3. Sentry
    try:
        from app.observability.sentry import init_sentry
        init_sentry(
            dsn=settings.SENTRY_DSN,
            environment=settings.APP_ENV,
            release=settings.APP_VERSION,
        )
    except Exception:
        logger.exception("init_sentry failed (non-fatal)")


def _wire_instrumentation(app: FastAPI) -> None:
    try:
        from app.observability.instrumentation import instrument_all
        instrument_all(app=app, engine=engine)
    except Exception:
        logger.exception("instrumentation failed (non-fatal)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    _init_observability()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # R34 — validate runtime config (fail-fast on critical)
    startup_report = None
    try:
        from app.observability.startup_validator import (
            validate_runtime_config,
            fail_fast,
        )
        startup_report = validate_runtime_config(settings)
        try:
            fail_fast(startup_report)
        except Exception as critical_exc:
            # Try to capture to Sentry before exiting
            try:
                from app.observability.sentry import capture_exception_safe
                capture_exception_safe(critical_exc)
            except Exception:
                pass
            logger.critical("startup config validation failed: %s", critical_exc)
            sys.exit(1)
    except Exception:
        logger.exception("startup validator itself raised (non-fatal)")

    # 1. Init database (create tables if not exist)
    await init_db()
    logger.info("Database initialized")

    # 2. Start background scheduler
    try:
        from app.core.scheduler import start_scheduler
        await start_scheduler()
        logger.info("Background scheduler started")
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")

    # 3. ML reactive event listener
    try:
        from app.services.ml_service import MLService
        asyncio.create_task(
            MLService(None).start_event_listener(),
            name="ml-event-listener",
        )
        logger.info("ML event listener task started")
    except Exception as e:
        logger.warning(f"ML event listener not started (non-fatal): {e}")

    # 4. Deployment Engine worker
    try:
        from app.core.deployment_engine.worker import run_deployment_worker
        asyncio.create_task(run_deployment_worker(), name="deployment-worker")
        logger.info("Deployment Engine worker started")
    except Exception as e:
        logger.warning(f"Deployment Engine worker not started (non-fatal): {e}")

    # 5. Event Bus WebSocket bridge
    try:
        from app.core.events.event_bus import event_bus
        event_bus.enable_ws_bridge()
        logger.info("Event Bus WebSocket bridge enabled")
    except Exception as e:
        logger.warning(f"Event Bus not started (non-fatal): {e}")

    # 6. K8s watcher bootstrap
    try:
        from app.core.events.k8s_watcher import bootstrap_watchers
        asyncio.create_task(bootstrap_watchers(), name="k8s-watcher-bootstrap")
        logger.info("Kubernetes cluster watcher bootstrap started")
    except Exception as e:
        logger.warning(f"K8s watcher bootstrap not started (non-fatal): {e}")

    # 7. Webhook routes
    try:
        from app.api.webhooks import github as github_wh, stripe as stripe_wh
        from app.api.webhooks import gitlab as gitlab_wh, slack as slack_wh
        app.include_router(github_wh.router, prefix="/webhooks", tags=["Webhooks-Inbound"])
        app.include_router(stripe_wh.router, prefix="/webhooks", tags=["Webhooks-Inbound"])
        app.include_router(gitlab_wh.router, prefix="/webhooks", tags=["Webhooks-Inbound"])
        app.include_router(slack_wh.router,  prefix="/webhooks", tags=["Webhooks-Inbound"])
    except Exception as e:
        logger.warning(f"Webhook routes not loaded: {e}")

    # Sprint 3 R38 — mark startup complete so /startup probe returns 200
    try:
        from app.api.v1.endpoints.health import mark_startup_complete
        mark_startup_complete(startup_report)
        logger.info("Startup complete")
    except Exception:
        logger.exception("mark_startup_complete failed (non-fatal)")

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

_wire_instrumentation(app)

# ── /metrics endpoint (Sprint 3 R31) ─────────────────────────────────────────
@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint():
    from app.observability.metrics import render_latest, content_type
    body = render_latest()
    return Response(content=body, media_type=content_type())

app.add_middleware(RateLimitMiddleware)
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
async def root_health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
        "websocket_connections": ws_manager.total_connections,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    from app.core.exceptions import UniOpsException
    if isinstance(exc, UniOpsException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.message, "code": exc.code},
        )
    # Sprint 3 R29 — capture unhandled exceptions to Sentry
    try:
        from app.observability.sentry import capture_exception_safe
        capture_exception_safe(exc)
    except Exception:
        pass
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error", "code": "INTERNAL_ERROR"},
    )