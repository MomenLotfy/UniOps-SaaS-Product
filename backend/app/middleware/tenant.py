"""Tenant Middleware — validates tenant context and enforces tenant isolation."""
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.logger import logger

TENANT_EXCLUDED_PREFIXES = (
    "/docs", "/redoc", "/openapi", "/health",
    "/api/v1/auth/", "/webhooks/",
)


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if any(path.startswith(prefix) for prefix in TENANT_EXCLUDED_PREFIXES):
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)

        if tenant_id and path.startswith("/api/"):
            path_tenant = self._extract_tenant_from_path(path)
            if path_tenant and path_tenant != tenant_id:
                logger.warning(
                    f"Tenant mismatch: token={tenant_id}, path={path_tenant} for {path}"
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "message": "Tenant access denied",
                        "code": "TENANT_MISMATCH",
                    },
                )

        return await call_next(request)

    def _extract_tenant_from_path(self, path: str) -> str:
        import re
        match = re.search(r"/tenants/([^/]+)", path)
        return match.group(1) if match else None
