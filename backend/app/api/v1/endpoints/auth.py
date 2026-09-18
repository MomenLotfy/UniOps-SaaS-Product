from __future__ import annotations
from typing import Annotated, Optional
from fastapi import APIRouter, Body, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import ip_rate_limit
from app.schemas.auth import (
    LoginRequest, RegisterRequest, TokenResponse,
    RefreshTokenRequest, ForgotPasswordRequest, ResetPasswordRequest,
    ChangePasswordRequest, TwoFactorSetupResponse, TwoFactorVerifyRequest,
)
from app.schemas.common import APIResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=APIResponse[TokenResponse],
             dependencies=[Depends(ip_rate_limit("auth.login", 10, 60))])
async def login(data: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    tokens = await service.login(data.email, data.password)
    return APIResponse(data=tokens)


@router.post("/register", response_model=APIResponse[TokenResponse],
             dependencies=[Depends(ip_rate_limit("auth.register", 5, 60))])
async def register(data: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    tokens = await service.register(data)
    return APIResponse(data=tokens)


@router.post("/refresh", response_model=APIResponse[TokenResponse])
async def refresh_token(data: RefreshTokenRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    tokens = await service.refresh(data.refresh_token)
    return APIResponse(data=tokens)


@router.post("/forgot-password", dependencies=[Depends(ip_rate_limit("auth.forgot", 5, 60))])
async def forgot_password(data: ForgotPasswordRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    await service.forgot_password(data.email)
    return APIResponse(message="Password reset email sent")


@router.post("/reset-password", dependencies=[Depends(ip_rate_limit("auth.reset", 5, 60))])
async def reset_password(data: ResetPasswordRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    await service.reset_password(data.token, data.new_password)
    return APIResponse(message="Password reset successfully")


@router.post("/logout")
async def logout(
    db: Annotated[AsyncSession, Depends(get_db)],
    data: Optional[RefreshTokenRequest] = Body(default=None),
    authorization: Optional[str] = Header(default=None),
):
    """Revoke the *refresh* token supplied in the request body.

    R1 fix: previously this handler blacklisted whatever was in the
    Authorization header (the access token) while ``/auth/refresh`` checks
    the blacklist against the refresh token — a logout therefore never
    actually invalidated the refresh token.  We blacklist the body-supplied
    refresh token; if the header ALSO happens to carry a refresh token we
    blacklist it too (some clients only send the header).  Access-token
    validity remains short by design (JWT exp) — we only ever blacklist
    refresh tokens here.
    """
    service = AuthService(db)
    tokens: list[str] = []
    if data is not None and data.refresh_token:
        tokens.append(data.refresh_token)
    if authorization and authorization.startswith("Bearer "):
        header_token = authorization.removeprefix("Bearer ").strip()
        if header_token and header_token not in tokens:
            try:
                from app.core.security import decode_token as _dec
                if _dec(header_token).get("type") == "refresh":
                    tokens.append(header_token)
            except ValueError:
                pass  # malformed header token — nothing to blacklist
    for tok in tokens:
        await service.logout(user_id="", refresh_token=tok)
    return APIResponse(message="Logged out successfully")


@router.post("/2fa/setup", response_model=APIResponse[TwoFactorSetupResponse])
async def setup_2fa(db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    result = await service.setup_2fa()
    return APIResponse(data=result)


@router.post("/2fa/verify", dependencies=[Depends(ip_rate_limit("auth.2fa", 10, 60))])
async def verify_2fa(data: TwoFactorVerifyRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    await service.verify_2fa(data.code)
    return APIResponse(message="2FA verified successfully")
