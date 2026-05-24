from __future__ import annotations
"""Users API — CRUD operations for tenant users, invitations, and role management."""
from typing import Optional
from fastapi import APIRouter, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession, Pagination
from app.schemas.user import UserUpdate, UserInvite, UserResponse, ChangePasswordRequest
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.user_service import UserService

router = APIRouter()


@router.get("", response_model=APIResponse[PaginatedResponse])
async def list_users(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    svc = UserService(db)
    result = await svc.list_users(tenant_id, page, page_size, search, role, is_active)
    return APIResponse(data=result)


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_me(current_user: CurrentUser, db: DBSession):
    svc = UserService(db)
    user = await svc.get_by_id(current_user["user_id"])
    return APIResponse(data=user)


@router.put("/me", response_model=APIResponse[UserResponse])
async def update_me(data: UserUpdate, current_user: CurrentUser, db: DBSession):
    svc = UserService(db)
    user = await svc.update(
        current_user["user_id"], data,
        current_user["user_id"], current_user.get("roles", []),
    )
    return APIResponse(data=user)


@router.post("/me/change-password", status_code=status.HTTP_200_OK)
async def change_password(data: ChangePasswordRequest, current_user: CurrentUser, db: DBSession):
    svc = UserService(db)
    await svc.change_password(current_user["user_id"], data)
    return APIResponse(message="Password changed successfully")


@router.get("/{user_id}", response_model=APIResponse[UserResponse])
async def get_user(user_id: str, current_user: AdminUser, db: DBSession):
    svc = UserService(db)
    user = await svc.get_by_id(user_id)
    return APIResponse(data=user)


@router.put("/{user_id}", response_model=APIResponse[UserResponse])
async def update_user(user_id: str, data: UserUpdate, current_user: AdminUser, db: DBSession):
    svc = UserService(db)
    user = await svc.update(user_id, data, current_user["user_id"], current_user.get("roles", []))
    return APIResponse(data=user)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def deactivate_user(user_id: str, current_user: AdminUser, db: DBSession):
    svc = UserService(db)
    await svc.deactivate(user_id)
    return APIResponse(message="User deactivated")


@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_user(data: UserInvite, current_user: AdminUser, tenant_id: TenantID, db: DBSession):
    svc = UserService(db)
    result = await svc.invite(tenant_id, data, current_user["user_id"])
    return APIResponse(data=result, message="Invitation sent")


@router.get("/me/sessions")
async def get_my_sessions(current_user: CurrentUser):
    """Return empty sessions list — session tracking not yet implemented."""
    return APIResponse(data=[])


@router.delete("/me/sessions/{session_id}")
async def revoke_session(session_id: str, current_user: CurrentUser):
    return APIResponse(data={"revoked": session_id})
