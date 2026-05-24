from __future__ import annotations
"""Webhooks API — manage outbound webhooks."""
from typing import Optional, List
from fastapi import APIRouter, Query, status
from pydantic import BaseModel
from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.webhook_service import WebhookService

router = APIRouter()


class WebhookCreate(BaseModel):
    name: str
    url: str
    events: List[str]
    secret: Optional[str] = None
    headers: Optional[dict] = None


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None
    headers: Optional[dict] = None


@router.get("", response_model=APIResponse[PaginatedResponse])
async def list_webhooks(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
):
    svc = WebhookService(db)
    result = await svc.list(tenant_id, page, page_size)
    return APIResponse(data=result)


@router.get("/{webhook_id}")
async def get_webhook(webhook_id: str, current_user: CurrentUser, db: DBSession):
    svc = WebhookService(db)
    webhook = await svc.get_by_id(webhook_id)
    return APIResponse(data=webhook)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_webhook(data: WebhookCreate, current_user: AdminUser, tenant_id: TenantID, db: DBSession):
    svc = WebhookService(db)
    webhook = await svc.create(tenant_id, data.name, data.url, data.events, data.secret, data.headers)
    return APIResponse(data=webhook, message="Webhook created")


@router.put("/{webhook_id}")
async def update_webhook(webhook_id: str, data: WebhookUpdate, current_user: AdminUser, db: DBSession):
    svc = WebhookService(db)
    webhook = await svc.update(webhook_id, data.model_dump(exclude_none=True))
    return APIResponse(data=webhook)


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str, current_user: AdminUser, db: DBSession):
    svc = WebhookService(db)
    await svc.delete(webhook_id)
    return APIResponse(message="Webhook deleted")


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: str, current_user: AdminUser, db: DBSession):
    svc = WebhookService(db)
    success = await svc.deliver(webhook_id, "test.ping", {"message": "UniOps webhook test"})
    return APIResponse(data={"delivered": success})
