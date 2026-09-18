"""Unit tests for user service logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.schemas.user import UserCreate, UserUpdate, ChangePasswordRequest
from app.core.exceptions import ConflictError, UnauthorizedError, ForbiddenError


class TestUserServiceGetByEmail:
    @pytest.mark.asyncio
    async def test_get_by_email_found(self):
        from app.services.user_service import UserService
        from app.models.user import User
        db = MagicMock()
        expected = MagicMock(email="found@test.com")
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = expected
        db.execute = AsyncMock(return_value=execute_result)
        svc = UserService(db)
        user = await svc.get_by_email("found@test.com")
        assert user is expected

    @pytest.mark.asyncio
    async def test_get_by_email_missing_returns_none(self):
        from app.services.user_service import UserService
        db = MagicMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=execute_result)
        svc = UserService(db)
        assert await svc.get_by_email("absent@test.com") is None

    @pytest.mark.asyncio
    async def test_invite_duplicate_email_raises(self):
        """Creation moved to AuthService.register / UserService.invite —
        duplicate detection is enforced there (e2e: tests/test_auth.py)."""
        from app.services.user_service import UserService
        from app.schemas.user import UserInvite
        db = MagicMock()
        svc = UserService(db)
        existing_user = MagicMock(email="taken@test.com")
        with patch.object(svc, "get_by_email", new_callable=AsyncMock, return_value=existing_user):
            with pytest.raises(ConflictError):
                await svc.invite("tenant-abc", UserInvite(
                    email="taken@test.com", role="developer", full_name="Taken User",
                ), "inviter-id")


class TestUserServiceUpdate:
    @pytest.mark.asyncio
    async def test_update_self_allowed(self):
        from app.services.user_service import UserService
        db = MagicMock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()
        svc = UserService(db)

        user = MagicMock()
        user.id = "user-123"
        user.tenant_id = "tenant-1"
        user.email = "old@test.com"
        user.username = "olduser"
        user.full_name = "Old Name"
        user.role = "viewer"
        user.is_active = True
        user.avatar_url = None
        user.is_verified = False
        user.two_factor_enabled = False
        user.preferences = {}
        from datetime import datetime, timezone
        user.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        user.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        with patch.object(svc, "_get_by_id", new_callable=AsyncMock, return_value=user):
            with patch.object(svc, "_update_fields", new_callable=AsyncMock) as upd:
                data = UserUpdate(full_name="New Name")
                await svc.update(
                    "user-123", data,
                    {"user_id": "user-123", "tenant_id": None, "roles": ["viewer"]},
                )
                upd.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_admin_can_update_other_user(self):
        from app.services.user_service import UserService
        db = MagicMock()
        svc = UserService(db)
        user = MagicMock()
        user.id = "user-999"
        user.tenant_id = "tenant-1"
        user.email = "other@test.com"
        user.username = "otheruser"
        user.full_name = "Other User"
        user.role = "viewer"
        user.is_active = True
        user.avatar_url = None
        user.is_verified = False
        user.two_factor_enabled = False
        user.preferences = {}
        from datetime import datetime, timezone
        user.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        user.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        with patch.object(svc, "_get_by_id", new_callable=AsyncMock, return_value=user):
            with patch.object(svc, "_update_fields", new_callable=AsyncMock) as upd:
                await svc.update(
                    "user-999", UserUpdate(full_name="X"),
                    {"user_id": "user-123", "tenant_id": "tenant-1", "roles": ["admin"]},
                )
                upd.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_other_user_without_admin_raises(self):
        from app.services.user_service import UserService
        db = MagicMock()
        svc = UserService(db)
        user = MagicMock()
        user.id = "user-999"

        user.tenant_id = "tenant-1"
        with patch.object(svc, "_get_by_id", new_callable=AsyncMock, return_value=user):
            with pytest.raises(ForbiddenError):
                await svc.update(
                    "user-999", UserUpdate(full_name="X"),
                    {"user_id": "user-123", "tenant_id": "tenant-1", "roles": ["viewer"]},
                )


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_wrong_password_raises(self):
        from app.services.user_service import UserService
        from app.core.security import hash_password
        db = MagicMock()
        db.flush = AsyncMock()
        svc = UserService(db)

        user = MagicMock()
        user.hashed_password = hash_password("correct_password")

        with patch.object(svc, "_get_by_id", new_callable=AsyncMock, return_value=user):
            with pytest.raises(UnauthorizedError):
                await svc.change_password("user-123", ChangePasswordRequest(
                    current_password="wrong", new_password="newpassword123"
                ))

    @pytest.mark.asyncio
    async def test_correct_password_succeeds(self):
        from app.services.user_service import UserService
        from app.core.security import hash_password
        db = MagicMock()
        db.flush = AsyncMock()
        svc = UserService(db)
        user = MagicMock()
        user.hashed_password = hash_password("correct_password")

        with patch.object(svc, "_get_by_id", new_callable=AsyncMock, return_value=user):
            await svc.change_password("user-123", ChangePasswordRequest(
                current_password="correct_password", new_password="new_secure_pass123"
            ))
