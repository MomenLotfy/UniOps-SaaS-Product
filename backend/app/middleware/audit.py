"""Audit Middleware — automatically logs API requests to the audit trail."""
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.logger import logger

AUDIT_EXCLUDED_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}
AUDIT_EXCLUDED_PREFIXES = ("/health", "/docs", "/redoc", "/openapi", "/static")


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if any(path.startswith(prefix) for prefix in AUDIT_EXCLUDED_PREFIXES):
            return await call_next(request)

        start_time = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            raise
        duration_ms = int((time.monotonic() - start_time) * 1000)

        user_id = getattr(request.state, "user_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)

        if not user_id or not tenant_id:
            return response

        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                resource = self._extract_resource(path)
                resource_id = self._extract_resource_id(path)
                action = f"{request.method}:{resource}"

                from app.core.database import AsyncSessionLocal
                from app.services.audit_service import AuditService
                async with AsyncSessionLocal() as db:
                    svc = AuditService(db)
                    await svc.log(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        action=action,
                        resource=resource,
                        resource_id=resource_id,
                        ip=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                        details={"method": request.method, "path": path, "duration_ms": duration_ms},
                        status="success" if response.status_code < 400 else "failure",
                    )
                    await db.commit()
            except Exception as e:
                logger.debug(f"Audit middleware error (non-fatal): {e}")

        return response

    def _extract_resource(self, path: str) -> str:
        parts = path.strip("/").split("/")
        resource_parts = [p for p in parts if not self._is_id(p) and p not in ("api", "v1")]
        return resource_parts[-1] if resource_parts else "unknown"

    def _extract_resource_id(self, path: str) -> str:
        import re
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        match = re.search(uuid_pattern, path, re.IGNORECASE)
        return match.group(0) if match else None

    def _is_id(self, part: str) -> bool:
        import re
        return bool(re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-", part, re.IGNORECASE))
