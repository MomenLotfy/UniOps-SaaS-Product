from typing import Annotated
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import UnauthorizedError, ForbiddenError

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise UnauthorizedError()
        return {"user_id": user_id, "payload": payload}
    except ValueError:
        raise UnauthorizedError("Invalid or expired token")


async def get_current_active_user(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    return current_user


async def require_admin(
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    roles = current_user.get("payload", {}).get("roles", [])
    if "admin" not in roles and "super_admin" not in roles:
        raise ForbiddenError("Admin access required")
    return current_user


async def get_tenant_id(
    current_user: Annotated[dict, Depends(get_current_active_user)],
) -> str:
    tenant_id = current_user.get("payload", {}).get("tenant_id")
    if not tenant_id:
        raise UnauthorizedError("Tenant not found in token")
    return tenant_id
