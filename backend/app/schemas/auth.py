from typing import Optional
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    password: str
    company_name: Optional[str] = None


# ── User info embedded in auth responses ──────────────────────────────────────
class UserInfo(BaseModel):
    """Minimal user record returned with every token response."""
    id: str
    email: str
    full_name: str
    username: str
    role: str
    tenant_id: str
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int          # seconds
    user: UserInfo           # ← ADDED: frontend needs this to build the user object


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code_url: str


class TwoFactorVerifyRequest(BaseModel):
    code: str
