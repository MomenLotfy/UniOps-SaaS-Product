from __future__ import annotations
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest, RegisterRequest, TokenResponse,
    RefreshTokenRequest, ForgotPasswordRequest, ResetPasswordRequest,
    ChangePasswordRequest, TwoFactorSetupResponse, TwoFactorVerifyRequest,
)
from app.schemas.common import APIResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(data: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    tokens = await service.login(data.email, data.password)
    return APIResponse(data=tokens)


@router.post("/register", response_model=APIResponse[TokenResponse])
async def register(data: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    tokens = await service.register(data)
    return APIResponse(data=tokens)


@router.post("/refresh", response_model=APIResponse[TokenResponse])
async def refresh_token(data: RefreshTokenRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    tokens = await service.refresh(data.refresh_token)
    return APIResponse(data=tokens)


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    await service.forgot_password(data.email)
    return APIResponse(message="Password reset email sent")


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    await service.reset_password(data.token, data.new_password)
    return APIResponse(message="Password reset successfully")


@router.post("/logout")
async def logout(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(default=None),
):
    refresh_token = ""
    if authorization and authorization.startswith("Bearer "):
        refresh_token = authorization.removeprefix("Bearer ").strip()
    service = AuthService(db)
    await service.logout(user_id="", refresh_token=refresh_token)
    return APIResponse(message="Logged out successfully")


@router.post("/2fa/setup", response_model=APIResponse[TwoFactorSetupResponse])
async def setup_2fa(db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    result = await service.setup_2fa()
    return APIResponse(data=result)


@router.post("/2fa/verify")
async def verify_2fa(data: TwoFactorVerifyRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    await service.verify_2fa(data.code)
    return APIResponse(message="2FA verified successfully")
