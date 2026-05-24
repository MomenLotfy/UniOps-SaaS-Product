"""
JWT Authentication Middleware — validates bearer tokens on protected routes.
Excluded paths (docs, health, auth endpoints) bypass validation.
"""
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import decode_token
from app.utils.logger import logger

EXCLUDED_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/webhooks/",
)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if any(path.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        if path.startswith("/ws/"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Authentication required", "code": "UNAUTHORIZED"},
            )

        token = auth_header[7:]
        try:
            payload = decode_token(token)
            request.state.user_id = payload.get("sub")
            request.state.tenant_id = payload.get("tenant_id")
            request.state.roles = payload.get("roles", [])
            request.state.token_payload = payload
        except ValueError as e:
            logger.warning(f"Auth middleware: invalid token from {request.client.host if request.client else 'unknown'}: {e}")
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Invalid or expired token", "code": "UNAUTHORIZED"},
            )

        return await call_next(request)
