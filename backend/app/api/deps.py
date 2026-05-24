"""
Shared FastAPI dependencies for API layer.
Re-exports core dependencies and adds API-specific ones.
"""
from typing import Annotated, Optional
from fastapi import Depends, Query, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.core.redis_client import get_redis
from app.core.pagination import PageParams
from app.config import settings

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if not credentials:
        raise UnauthorizedError("Bearer token required")
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise UnauthorizedError("Invalid token payload")
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "tenant_id": payload.get("tenant_id"),
            "roles": payload.get("roles", []),
            "payload": payload,
        }
    except ValueError as e:
        raise UnauthorizedError(str(e))


async def get_current_active_user(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    return current_user


async def require_admin(
    current_user: Annotated[dict, Depends(get_current_active_user)],
) -> dict:
    roles = current_user.get("roles", [])
    if not any(r in roles for r in ("admin", "super_admin")):
        raise ForbiddenError("Admin access required")
    return current_user


async def require_super_admin(
    current_user: Annotated[dict, Depends(get_current_active_user)],
) -> dict:
    if "super_admin" not in current_user.get("roles", []):
        raise ForbiddenError("Super admin access required")
    return current_user


async def get_tenant_id(
    current_user: Annotated[dict, Depends(get_current_active_user)],
) -> str:
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise UnauthorizedError("Tenant context not found in token")
    return tenant_id


def get_pagination(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


CurrentUser = Annotated[dict, Depends(get_current_active_user)]
AdminUser = Annotated[dict, Depends(require_admin)]
SuperAdminUser = Annotated[dict, Depends(require_super_admin)]
TenantID = Annotated[str, Depends(get_tenant_id)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
Pagination = Annotated[PageParams, Depends(get_pagination)]
