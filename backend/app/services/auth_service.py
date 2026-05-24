from __future__ import annotations
"""Authentication service — login, registration, password reset, 2FA."""
from datetime import timedelta
import uuid, secrets, json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.tenant import Tenant
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.exceptions import UnauthorizedError, ConflictError, NotFoundError
from app.schemas.auth import RegisterRequest, TokenResponse, TwoFactorSetupResponse, UserInfo
from app.config import settings
from app.services.base import BaseService
from app.utils.logger import logger

# TTLs
_RESET_TOKEN_TTL  = 60 * 60        # 1 hour
_INVITE_TOKEN_TTL = 60 * 60 * 48   # 48 hours

# Redis key helpers
def _reset_key(token: str)  -> str: return f"uniops:reset:{token}"
def _invite_key(token: str) -> str: return f"uniops:invite:{token}"


async def _redis_set(key: str, value: str, ttl: int) -> None:
    try:
        from app.core.redis_client import cache_set
        await cache_set(key, value, ttl)
    except Exception as e:
        logger.warning(f"Redis set failed, falling back to memory: {e}")
        _memory_fallback[key] = value

async def _redis_get(key: str) -> str | None:
    try:
        from app.core.redis_client import cache_get
        return await cache_get(key)
    except Exception as e:
        logger.warning(f"Redis get failed, using memory fallback: {e}")
        return _memory_fallback.get(key)

async def _redis_del(key: str) -> None:
    try:
        from app.core.redis_client import cache_delete
        await cache_delete(key)
    except Exception:
        _memory_fallback.pop(key, None)

# Memory fallback (only used if Redis is unreachable)
_memory_fallback: dict[str, str] = {}


class AuthService(BaseService):

    async def login(self, email: str, password: str) -> TokenResponse:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedError("Account is disabled")
        logger.info(f"User {email} logged in successfully")
        return self._create_tokens(user)

    async def register(self, data: RegisterRequest) -> TokenResponse:
        # Check duplicate email
        result = await self.db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise ConflictError("Email already registered")

        # Check invite token if provided
        invite_data = None
        if hasattr(data, "invite_token") and data.invite_token:
            raw = await _redis_get(_invite_key(data.invite_token))
            if raw:
                invite_data = json.loads(raw)
                await _redis_del(_invite_key(data.invite_token))

        # Create tenant (or use from invite)
        if invite_data:
            tenant_id = invite_data["tenant_id"]
            role = invite_data["role"]
            tenant = await self._get_by_id(Tenant, tenant_id)
        else:
            slug = data.username.lower().replace(" ", "-")[:50]
            slug_check = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
            if slug_check.scalar_one_or_none():
                slug = f"{slug}-{uuid.uuid4().hex[:6]}"

            company_name = getattr(data, "company_name", None) or f"{data.full_name}'s Organization"
            tenant = Tenant(
                name=company_name,
                slug=slug,
                plan="free",
                is_active=True,
            )
            self.db.add(tenant)
            await self.db.flush()
            tenant_id = tenant.id
            role = "admin"

        user = User(
            tenant_id       = tenant_id,
            email           = data.email,
            username        = data.username,
            full_name       = data.full_name,
            hashed_password = hash_password(data.password),
            role            = role,
            is_active       = True,
            is_verified     = False,
        )
        self.db.add(user)
        await self.db.flush()

        logger.info(f"New user registered: {data.email} (tenant: {tenant.name})")

        # Send welcome email (non-blocking)
        try:
            from app.services.notification_service import NotificationService
            notif = NotificationService()
            await notif.send_welcome(
                to_email     = user.email,
                user_name    = user.full_name,
                company_name = tenant.name,
            )
        except Exception as e:
            logger.warning(f"Welcome email failed (non-fatal): {e}")

        return self._create_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            # Check if token is blacklisted (logged out)
            blacklisted = await _redis_get(f"uniops:blacklist:{refresh_token}")
            if blacklisted:
                raise UnauthorizedError("Token has been revoked")

            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise UnauthorizedError("Invalid refresh token type")
            user_id = payload.get("sub")
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user or not user.is_active:
                raise UnauthorizedError("User not found or inactive")
            return self._create_tokens(user)
        except ValueError:
            raise UnauthorizedError("Invalid or expired refresh token")

    async def forgot_password(self, email: str) -> None:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            return   # silent — don't reveal if email exists

        reset_token = secrets.token_urlsafe(32)
        await _redis_set(_reset_key(reset_token), user.id, _RESET_TOKEN_TTL)
        logger.info(f"Password reset token for {email}: {reset_token[:8]}...")

        try:
            from app.services.notification_service import NotificationService
            await NotificationService().send_password_reset(
                to_email   = user.email,
                user_name  = user.full_name,
                reset_token= reset_token,
            )
        except Exception as e:
            logger.warning(f"Password reset email failed (non-fatal): {e}")

    async def reset_password(self, token: str, new_password: str) -> None:
        user_id = await _redis_get(_reset_key(token))
        if not user_id:
            raise UnauthorizedError("Invalid or expired reset token")
        await _redis_del(_reset_key(token))

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)

        user.hashed_password = hash_password(new_password)
        await self.db.flush()
        logger.info(f"Password reset for user {user_id}")

    async def setup_2fa(self, user_id: str) -> TwoFactorSetupResponse:
        secret = secrets.token_hex(10).upper()
        return TwoFactorSetupResponse(
            secret      = secret,
            qr_code_url = f"otpauth://totp/UniOps?secret={secret}&issuer=UniOps",
        )

    async def verify_2fa(self, user_id: str, code: str) -> None:
        """Verify a TOTP code using pyotp."""
        import pyotp
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not getattr(user, "totp_secret", None):
            raise UnauthorizedError("2FA not configured for this user")
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(code, valid_window=1):
            raise UnauthorizedError("Invalid 2FA code")

    async def logout(self, user_id: str, refresh_token: str) -> None:
        """Blacklist the refresh token in Redis for the remainder of its TTL."""
        try:
            payload = decode_token(refresh_token)
            exp = payload.get("exp", 0)
            import time
            ttl = max(int(exp - time.time()), 1)
            await _redis_set(f"uniops:blacklist:{refresh_token}", "1", ttl)
        except Exception as e:
            logger.warning(f"Logout blacklist failed (non-fatal): {e}")

    def _create_tokens(self, user: User) -> TokenResponse:
        """Create access + refresh tokens and embed the user info in the response."""
        access = create_access_token(
            user_id   = user.id,
            email     = user.email,
            tenant_id = user.tenant_id,
            roles     = [user.role],
        )
        refresh = create_refresh_token(user_id=user.id)

        user_info = UserInfo(
            id          = user.id,
            email       = user.email,
            full_name   = user.full_name,
            username    = user.username,
            role        = user.role,
            tenant_id   = user.tenant_id,
            is_active   = user.is_active,
            is_verified = user.is_verified,
            avatar_url  = user.avatar_url,
        )

        return TokenResponse(
            access_token  = access,
            refresh_token = refresh,
            expires_in    = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user          = user_info,
        )

    @staticmethod
    async def create_invite_token(email: str, role: str, tenant_id: str, invited_by: str) -> str:
        """Create a signed invite token stored in Redis with 48-hour TTL."""
        token = secrets.token_urlsafe(32)
        payload = json.dumps({
            "email":      email,
            "role":       role,
            "tenant_id":  tenant_id,
            "invited_by": invited_by,
        })
        await _redis_set(_invite_key(token), payload, _INVITE_TOKEN_TTL)
        return token
