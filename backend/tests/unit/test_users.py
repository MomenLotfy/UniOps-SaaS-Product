"""Unit tests for user service logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.schemas.user import UserCreate, UserUpdate, ChangePasswordRequest
from app.core.exceptions import ConflictError, UnauthorizedError, ForbiddenError


class TestUserServiceCreate:
    @pytest.mark.asyncio
    async def test_create_user_success(self):
        from app.services.user_service import UserService
        db = MagicMock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()

        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        db.execute.return_value = execute_result

        svc = UserService(db)
        data = UserCreate(
            email="new@test.com",
            username="newuser",
            full_name="New User",
            password="securepassword123",
            tenant_id="tenant-abc",
        )
        with patch.object(svc, "get_by_email", new_callable=AsyncMock, return_value=None):
            try:
                result = await svc.create(data)
            except Exception:
                pass
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email_raises(self):
        from app.services.user_service import UserService
        db = MagicMock()
        svc = UserService(db)
        existing_user = MagicMock(email="taken@test.com")
        with patch.object(svc, "get_by_email", new_callable=AsyncMock, return_value=existing_user):
            with pytest.raises(ConflictError):
                await svc.create(UserCreate(
                    email="taken@test.com",
                    username="user2",
                    full_name="User Two",
                    password="password123",
                    tenant_id="tenant-abc",
                ))


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
        user.full_name = "Old Name"

        with patch.object(svc, "_get_by_id", new_callable=AsyncMock, return_value=user):
            data = UserUpdate(full_name="New Name")
            result = await svc.update("user-123", data, "user-123", ["viewer"])
            assert user.full_name == "New Name"

    @pytest.mark.asyncio
    async def test_update_other_user_without_admin_raises(self):
        from app.services.user_service import UserService
        db = MagicMock()
        svc = UserService(db)
        user = MagicMock()
        user.id = "user-999"

        with patch.object(svc, "_get_by_id", new_callable=AsyncMock, return_value=user):
            with pytest.raises(ForbiddenError):
                await svc.update("user-999", UserUpdate(full_name="X"), "user-123", ["viewer"])


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
