from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: str


class UserCreate(UserBase):
    password: str
    role: str = "viewer"
    tenant_id: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = None
    preferences: Optional[dict] = None
    is_active: Optional[bool] = None


class UserInvite(BaseModel):
    email: EmailStr
    role: str = "viewer"
    full_name: str


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    email: str
    username: str
    full_name: str
    role: str
    avatar_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    two_factor_enabled: bool
    preferences: dict = {}
    created_at: datetime
    updated_at: datetime


class UserProfile(UserResponse):
    pass


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class APIKeyCreate(BaseModel):
    name: str
    expires_in_days: Optional[int] = 90


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
