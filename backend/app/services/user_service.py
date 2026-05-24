from __future__ import annotations
"""User service — CRUD, invitations, role management."""
import secrets
from typing import Optional
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.user import UserUpdate, UserInvite, UserResponse, ChangePasswordRequest
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundError, ConflictError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.services.base import BaseService
from app.utils.logger import logger


class UserService(BaseService):

    async def list_users(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> PaginatedResponse:
        query = select(User).where(User.tenant_id == tenant_id)
        if search:
            query = query.where(or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%"),
            ))
        if role:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        total = await self._count(query)
        query = query.order_by(User.created_at.desc())
        items = await self._paginate(query, page, page_size)

        return PaginatedResponse(
            data     = [UserResponse.model_validate(u) for u in items],
            total    = total,
            page     = page,
            page_size= page_size,
            pages    = (total + page_size - 1) // page_size,
        )

    async def get_by_id(self, user_id: str) -> UserResponse:
        user = await self._get_by_id(User, user_id)
        return UserResponse.model_validate(user)

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update(self, user_id: str, data: UserUpdate, requesting_user: dict) -> UserResponse:
        user = await self._get_by_id(User, user_id)

        # Only admin can change role or deactivate others
        if data.role and data.role != user.role:
            if "admin" not in requesting_user.get("roles", []):
                raise UnauthorizedError("Only admins can change roles")

        update_data = data.model_dump(exclude_none=True)
        await self._update_fields(user, update_data)
        return UserResponse.model_validate(user)

    async def change_password(self, user_id: str, data: ChangePasswordRequest) -> None:
        user = await self._get_by_id(User, user_id)
        if not verify_password(data.current_password, user.hashed_password):
            raise UnauthorizedError("Current password is incorrect")
        user.hashed_password = hash_password(data.new_password)
        await self.db.flush()

    async def invite(self, tenant_id: str, data: UserInvite, invited_by_user_id: str) -> dict:
        # Check user doesn't already exist
        existing = await self.get_by_email(data.email)
        if existing:
            raise ConflictError(f"User with email {data.email} already exists")

        # Get inviting user info
        inviter = await self._get_by_id(User, invited_by_user_id)
        tenant_r = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant   = tenant_r.scalar_one_or_none()

        # Create invite token
        from app.services.auth_service import AuthService
        token = await AuthService.create_invite_token(
            email      = data.email,
            role       = data.role,
            tenant_id  = tenant_id,
            invited_by = invited_by_user_id,
        )

        # Send invite email
        try:
            from app.services.notification_service import NotificationService
            await NotificationService().send_invite(
                to_email        = data.email,
                invited_by_name = inviter.full_name,
                company_name    = tenant.name if tenant else "UniOps",
                role            = data.role,
                invite_token    = token,
            )
            logger.info(f"Invitation sent to {data.email} (role={data.role})")
        except Exception as e:
            logger.error(f"Invite email failed: {e}")

        return {
            "email":   data.email,
            "role":    data.role,
            "token":   token,
            "message": f"Invitation sent to {data.email}",
        }

    async def deactivate(self, user_id: str) -> UserResponse:
        user = await self._get_by_id(User, user_id)
        user.is_active = False
        await self.db.flush()
        return UserResponse.model_validate(user)

    async def get_stats(self, tenant_id: str) -> dict:
        result = await self.db.execute(
            select(User.role, User.is_active, func.count(User.id))
            .where(User.tenant_id == tenant_id)
            .group_by(User.role, User.is_active)
        )
        rows = result.fetchall()
        total = active = admin_count = 0
        for role, is_active, count in rows:
            total += count
            if is_active:
                active += count
            if role == "admin":
                admin_count += count
        return {
            "total":   total,
            "active":  active,
            "inactive": total - active,
            "admins":  admin_count,
        }
