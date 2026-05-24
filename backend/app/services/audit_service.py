from __future__ import annotations
"""Audit service — records and queries audit log entries."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.schemas.common import PaginatedResponse
from app.services.base import BaseService


class AuditService(BaseService):
    async def log(
        self,
        tenant_id: str,
        user_id: Optional[str],
        action: str,
        resource: str,
        resource_id: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[dict] = None,
        status: str = "success",
    ) -> None:
        entry = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            ip=ip,
            user_agent=user_agent,
            details=details or {},
            status=status,
        )
        self.db.add(entry)
        await self.db.flush()

    async def list(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> PaginatedResponse:
        query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action.ilike(f"%{action}%"))
        if resource:
            query = query.where(AuditLog.resource == resource)
        if status:
            query = query.where(AuditLog.status == status)
        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)

        total = await self._count(query)
        query = query.order_by(AuditLog.created_at.desc())
        items = await self._paginate(query, page, page_size)

        return PaginatedResponse(
            data=[i.to_dict() for i in items],
            total=total, page=page, page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def get_activity_summary(self, tenant_id: str, days: int = 7) -> dict:
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(AuditLog.action, func.count(AuditLog.id))
            .where(AuditLog.tenant_id == tenant_id, AuditLog.created_at >= since)
            .group_by(AuditLog.action)
            .order_by(func.count(AuditLog.id).desc())
            .limit(10)
        )
        top_actions = {row[0]: row[1] for row in result.fetchall()}

        user_result = await self.db.execute(
            select(AuditLog.user_id, func.count(AuditLog.id))
            .where(AuditLog.tenant_id == tenant_id, AuditLog.created_at >= since)
            .group_by(AuditLog.user_id)
            .order_by(func.count(AuditLog.id).desc())
            .limit(5)
        )
        top_users = {row[0]: row[1] for row in user_result.fetchall() if row[0]}

        return {
            "period_days": days,
            "top_actions": top_actions,
            "top_users": top_users,
        }
