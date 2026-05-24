from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel as PydanticModel
from sqlalchemy import select, delete as sql_delete

from app.api.deps import CurrentUser, TenantID, DBSession
from app.models.api_key import ApiKey
from app.schemas.common import APIResponse

router = APIRouter()


class CreateApiKeyRequest(PydanticModel):
    name: str
    scopes: list[str] = []
    expires_at: str | None = None


@router.get("")
async def list_api_keys(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    result = await db.execute(
        select(ApiKey)
        .where(
            ApiKey.tenant_id == tenant_id,
            ApiKey.user_id   == current_user["user_id"],
            ApiKey.is_active == True,
        )
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return APIResponse(data=[{
        "id":         k.id,
        "name":       k.name,
        "prefix":     k.key_prefix,
        "scopes":     k.scopes or [],
        "last_used":  k.last_used.isoformat()  if k.last_used  else None,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "created_at": k.created_at.isoformat(),
        "active":     k.is_active,
    } for k in keys])


@router.post("")
async def create_api_key(
    data: CreateApiKeyRequest,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    raw_key   = f"uo_live_{secrets.token_urlsafe(32)}"
    key_hash  = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:20]

    expires: datetime | None = None
    if data.expires_at:
        try:
            expires = datetime.fromisoformat(data.expires_at)
        except Exception:
            pass

    api_key = ApiKey(
        tenant_id  = tenant_id,
        user_id    = current_user["user_id"],
        name       = data.name,
        key_hash   = key_hash,
        key_prefix = key_prefix,
        scopes     = data.scopes,
        expires_at = expires,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return APIResponse(data={
        "id":         api_key.id,
        "name":       api_key.name,
        "key":        raw_key,
        "prefix":     key_prefix,
        "scopes":     api_key.scopes or [],
        "created_at": api_key.created_at.isoformat(),
    })


@router.delete("/{key_id}")
async def delete_api_key(key_id: str, current_user: CurrentUser, db: DBSession):
    await db.execute(
        sql_delete(ApiKey).where(
            ApiKey.id      == key_id,
            ApiKey.user_id == current_user["user_id"],
        )
    )
    await db.commit()
    return APIResponse(message="API key deleted")
