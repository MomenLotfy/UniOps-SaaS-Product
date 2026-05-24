"""Unit tests for authentication and JWT utilities."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token,
)


class TestPasswordHashing:
    def test_hash_password_returns_string(self):
        hashed = hash_password("testpassword123")
        assert isinstance(hashed, str)
        assert len(hashed) > 30

    def test_hash_is_unique_for_same_password(self):
        p = "samepassword"
        h1 = hash_password(p)
        h2 = hash_password(p)
        assert h1 != h2

    def test_verify_correct_password(self):
        pwd = "secure123!!"
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_verify_empty_password(self):
        hashed = hash_password("real_password")
        assert verify_password("", hashed) is False


class TestJWT:
    def test_create_access_token(self):
        token = create_access_token(
            user_id="user-123",
            email="user@test.com",
            tenant_id="tenant-abc",
            roles=["admin"],
        )
        assert isinstance(token, str)
        assert len(token) > 50

    def test_decode_valid_token(self):
        token = create_access_token(
            user_id="user-123",
            email="user@test.com",
            tenant_id="tenant-abc",
            roles=["admin"],
        )
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "user@test.com"
        assert payload["tenant_id"] == "tenant-abc"
        assert "admin" in payload["roles"]

    def test_decode_expired_token_raises(self):
        with patch("app.core.security.datetime") as mock_dt:
            past = datetime(2020, 1, 1, tzinfo=timezone.utc)
            mock_dt.now.return_value = past
            token = create_access_token(
                user_id="user-123",
                email="test@test.com",
                tenant_id="tenant-abc",
                roles=[],
            )
        with pytest.raises(ValueError, match="expired"):
            decode_token(token)

    def test_create_refresh_token(self):
        token = create_refresh_token(user_id="user-456")
        assert isinstance(token, str)
        payload = decode_token(token)
        assert payload["sub"] == "user-456"
        assert payload.get("type") == "refresh"

    def test_invalid_token_raises(self):
        with pytest.raises(ValueError):
            decode_token("not.a.valid.token")

    def test_tampered_token_raises(self):
        token = create_access_token("u1", "u@t.com", "t1", [])
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(ValueError):
            decode_token(tampered)
