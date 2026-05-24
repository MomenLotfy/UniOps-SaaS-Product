from __future__ import annotations
"""Alert service — manages alert lifecycle, notifications, and bulk operations."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.schemas.alert import AlertResponse, AlertUpdate, AlertStats
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundError
from app.services.base import BaseService


class AlertService(BaseService):
    async def list(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        is_read: Optional[bool] = None,
    ) -> PaginatedResponse:
        query = select(Alert).where(Alert.tenant_id == tenant_id)
        if severity:
            query = query.where(Alert.severity == severity)
        if status:
            query = query.where(Alert.status == status)
        if category:
            query = query.where(Alert.category == category)
        if is_read is not None:
            query = query.where(Alert.is_read == is_read)

        total = await self._count(query)
        query = query.order_by(Alert.created_at.desc())
        items = await self._paginate(query, page, page_size)

        return PaginatedResponse(
            data=[AlertResponse.model_validate(i) for i in items],
            total=total, page=page, page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def get_by_id(self, alert_id: str) -> AlertResponse:
        alert = await self._get_by_id(Alert, alert_id)
        return AlertResponse.model_validate(alert)

    async def update(self, alert_id: str, data: AlertUpdate) -> AlertResponse:
        alert = await self._get_by_id(Alert, alert_id)
        if data.status is not None:
            alert.status = data.status
            if data.status == "resolved" and not alert.resolved_at:
                alert.resolved_at = datetime.now(timezone.utc)
        if data.is_read is not None:
            alert.is_read = data.is_read
        await self.db.flush()
        return AlertResponse.model_validate(alert)

    async def mark_all_read(self, tenant_id: str) -> int:
        result = await self.db.execute(
            update(Alert)
            .where(Alert.tenant_id == tenant_id, Alert.is_read == False)
            .values(is_read=True)
        )
        await self.db.flush()
        return result.rowcount

    async def resolve_all(self, tenant_id: str, category: Optional[str] = None) -> int:
        query = update(Alert).where(
            Alert.tenant_id == tenant_id, Alert.status == "active"
        )
        if category:
            query = query.where(Alert.category == category)
        result = await self.db.execute(
            query.values(status="resolved", resolved_at=datetime.now(timezone.utc))
        )
        await self.db.flush()
        return result.rowcount

    async def get_stats(self, tenant_id: str) -> AlertStats:
        result = await self.db.execute(
            select(Alert.severity, Alert.status, Alert.is_read, func.count(Alert.id))
            .where(Alert.tenant_id == tenant_id)
            .group_by(Alert.severity, Alert.status, Alert.is_read)
        )
        rows = result.fetchall()
        stats = AlertStats()
        for severity, status, is_read, count in rows:
            stats.total += count
            if status == "active": stats.active += count
            if status == "resolved": stats.resolved += count
            if severity == "critical": stats.critical += count
            if severity == "high": stats.high += count
            if not is_read: stats.unread += count
        return stats

    async def create_and_notify(self, tenant_id: str, data: dict) -> AlertResponse:
        """Create a new alert and send notifications."""
        from app.models.alert import Alert
        from datetime import datetime, timezone

        alert = Alert(
            tenant_id = tenant_id,
            title     = data.get("title", "Alert"),
            message   = data.get("message", data.get("description", "")),
            severity  = data.get("severity", "medium"),
            category  = data.get("category", "general"),
            source    = data.get("source", "system"),
            status    = "active",
            is_read   = False,
            resource  = data.get("resource"),
            fired_at  = datetime.now(timezone.utc),
        )
        self.db.add(alert)
        await self.db.flush()

        alert_dict = {
            "id":       alert.id,
            "title":    alert.title,
            "message":  alert.message,
            "severity": alert.severity,
            "category": alert.category,
        }

        # Fire-and-forget notifications
        try:
            from app.services.notification_service import NotificationService
            await NotificationService().notify_alert(tenant_id, alert_dict)
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"Alert notification failed (non-fatal): {e}")

        return AlertResponse.model_validate(alert)
