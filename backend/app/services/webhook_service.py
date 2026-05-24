from __future__ import annotations
"""Webhook service — outbound webhook delivery with retry and signature."""
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.models.webhook import Webhook
from app.core.exceptions import NotFoundError
from app.schemas.common import PaginatedResponse
from app.services.base import BaseService
from app.utils.logger import logger


class WebhookService(BaseService):
    async def list(self, tenant_id: str, page: int = 1, page_size: int = 20) -> PaginatedResponse:
        from app.models.webhook import Webhook
        query = select(Webhook).where(Webhook.tenant_id == tenant_id)
        total = await self._count(query)
        items = await self._paginate(query.order_by(Webhook.created_at.desc()), page, page_size)
        return PaginatedResponse(
            data=[i.to_dict() for i in items],
            total=total, page=page, page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def get_by_id(self, webhook_id: str) -> dict:
        webhook = await self._get_by_id(Webhook, webhook_id)
        return webhook.to_dict()

    async def create(self, tenant_id: str, name: str, url: str, events: list, secret: Optional[str] = None, headers: Optional[dict] = None) -> dict:
        webhook = Webhook(
            tenant_id=tenant_id,
            name=name,
            url=url,
            events=events,
            secret=secret,
            headers=headers or {},
            is_active=True,
        )
        self.db.add(webhook)
        await self.db.flush()
        return webhook.to_dict()

    async def update(self, webhook_id: str, data: dict) -> dict:
        webhook = await self._get_by_id(Webhook, webhook_id)
        await self._update_fields(webhook, data)
        return webhook.to_dict()

    async def delete(self, webhook_id: str) -> None:
        webhook = await self._get_by_id(Webhook, webhook_id)
        await self.db.delete(webhook)
        await self.db.flush()

    async def deliver(self, webhook_id: str, event_type: str, payload: dict) -> bool:
        webhook = await self._get_by_id(Webhook, webhook_id)
        if not webhook.is_active:
            return False
        if event_type not in webhook.events and "*" not in webhook.events:
            return False

        body = json.dumps({"event": event_type, "data": payload, "timestamp": datetime.now(timezone.utc).isoformat()})
        headers = {"Content-Type": "application/json", **webhook.headers}

        if webhook.secret:
            sig = hmac.new(webhook.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-UniOps-Signature"] = f"sha256={sig}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook.url, content=body, headers=headers)
                webhook.last_response_code = response.status_code
                if response.status_code >= 400:
                    webhook.failure_count = (webhook.failure_count or 0) + 1
                else:
                    webhook.failure_count = 0
                await self.db.flush()
                return response.status_code < 400
        except Exception as e:
            logger.error(f"Webhook delivery failed for {webhook_id}: {e}")
            webhook.failure_count = (webhook.failure_count or 0) + 1
            await self.db.flush()
            return False

    async def deliver_to_all(self, tenant_id: str, event_type: str, payload: dict) -> dict:
        result = await self.db.execute(
            select(Webhook).where(
                Webhook.tenant_id == tenant_id,
                Webhook.is_active == True,
            )
        )
        webhooks = result.scalars().all()
        delivered, failed = 0, 0
        for wh in webhooks:
            if event_type in wh.events or "*" in wh.events:
                success = await self.deliver(wh.id, event_type, payload)
                if success: delivered += 1
                else: failed += 1
        return {"delivered": delivered, "failed": failed}
