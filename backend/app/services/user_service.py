from __future__ import annotations
"""User service — CRUD, invitations, role management."""
import secrets
from typing import Optional
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.tenant import Tenant
from app.core.exceptions import ForbiddenError
from app.schemas.user import UserUpdate, UserInvite, UserResponse, ChangePasswordRequest
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundError, ConflictError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.services.base import BaseService
from app.utils.logger import logger



def _assert_tenant(obj, tenant_id):
    """IDOR guard: id-addressed accessors verify ownership before returning."""
    from app.core.exceptions import NotFoundError
    if tenant_id is not None and getattr(obj, "tenant_id", None) is not None and obj.tenant_id != tenant_id:
        raise NotFoundError("Resource not found")

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

    async def get_by_id(self, user_id: str, tenant_id: str | None = None) -> UserResponse:
        user = await self._get_by_id(User, user_id)
        _assert_tenant(user, tenant_id)
        return UserResponse.model_validate(user)

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update(self, user_id: str, data: UserUpdate, requesting_user: dict) -> UserResponse:
        user = await self._get_by_id(User, user_id)

        roles = requesting_user.get("roles", []) or []
        is_self = requesting_user.get("user_id") == user_id
        is_admin = "admin" in roles or "super_admin" in roles

        # Only self or an admin may modify a user's profile (403, not silent permit)
        if not (is_self or is_admin):
            raise ForbiddenError("You can only update your own profile")

        # Tenant isolation: non-super-admin users must stay inside their tenant
        tenant_id = requesting_user.get("tenant_id")
        if tenant_id and "super_admin" not in roles and str(user.tenant_id) != str(tenant_id):
            raise ForbiddenError("Cross-tenant user modification is not allowed")

        # Only admin can change role or deactivate others
        if data.role and data.role != user.role:
            if not is_admin:
                raise ForbiddenError("Only admins can change roles")

        update_data = data.model_dump(exclude_none=True)
        # New data ALWAYS canonical — migrate legacy names at write time
        if update_data.get("role"):
            from app.constants.roles import normalize_role
            update_data["role"] = normalize_role(update_data["role"])
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

    async def deactivate(self, user_id: str, tenant_id: str | None = None) -> UserResponse:
        user = await self._get_by_id(User, user_id)
        _assert_tenant(user, tenant_id)
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

    async def list_invitations(self, tenant_id: str) -> list[dict]:
        """Tenant-scoped view of pending invites in Redis (uniops:invite:*)."""
        import hashlib, json
        from datetime import datetime, timezone
        from app.core.redis_client import get_redis
        from app.services import auth_service as _asvc

        results: list[dict] = []
        now = datetime.now(timezone.utc)
        raw: dict[str, str] = {}
        try:
            redis = await get_redis()
            if redis is not None:
                async for key in redis.scan_iter("uniops:invite:*"):
                    val = await redis.get(key)
                    if val:
                        raw[key if isinstance(key, str) else key.decode()] = val if isinstance(val, str) else val.decode()
        except Exception:
            raw = {}
        # memory fallback (dev/test without Redis)
        for k, v in list(_asvc._memory_fallback.items()):
            if k.startswith("uniops:invite:"):
                raw.setdefault(k, v)

        for key, val in raw.items():
            try:
                payload = json.loads(val)
            except Exception:
                continue
            if payload.get("tenant_id") != tenant_id:
                continue
            token = key.split("uniops:invite:", 1)[-1]
            results.append({
                "id": hashlib.sha256(token.encode()).hexdigest()[:16],
                "email": payload.get("email"),
                "role": payload.get("role"),
                "invited_by": payload.get("invited_by"),
                "status": "pending",
                "created_at": now.isoformat(),
            })
        return sorted(results, key=lambda r: r["email"] or "")

    async def revoke_invitation(self, tenant_id: str, token_hash: str) -> bool:
        """Delete the tenant's pending invite identified by its token hash.
        Never trusts a raw token from the client — hash-compare only."""
        import hashlib, json
        from app.core.redis_client import get_redis
        from app.services import auth_service as _asvc

        candidates: list[str] = [k for k in _asvc._memory_fallback.keys()
                                 if k.startswith("uniops:invite:")]
        try:
            redis = await get_redis()
            if redis is not None:
                async for key in redis.scan_iter("uniops:invite:*"):
                    candidates.append(key if isinstance(key, str) else key.decode())
        except Exception:
            pass

        for key in set(candidates):
            tok = key.split("uniops:invite:", 1)[-1]
            if hashlib.sha256(tok.encode()).hexdigest()[:16] != token_hash:
                continue
            # hash matches — verify tenant ownership before deleting
            val = None
            try:
                redis = await get_redis()
                if redis is not None:
                    val = await redis.get(key)
            except Exception:
                pass
            if val is None:
                val = _asvc._memory_fallback.get(key)
            if val is None:
                return False
            try:
                payload = json.loads(val)
            except Exception:
                return False
            if payload.get("tenant_id") != tenant_id:
                return False
            await _asvc._redis_del(key)  # graceful Redis-or-memory delete
            return True
        return False
