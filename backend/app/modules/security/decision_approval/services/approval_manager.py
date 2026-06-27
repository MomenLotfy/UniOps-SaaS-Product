"""
Approval Manager — public lifecycle API.

Mirrors `DecisionStrategyManager`.  Provides the higher-level methods
that orchestrate lifecycle transitions and version snapshots.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ApprovalState
from .approval_audit_service import ApprovalAuditService
from .approval_lifecycle_manager import ApprovalLifecycleManager
from .approval_repository import ApprovalRepository
from .approval_version_manager import ApprovalVersionManager

logger = logging.getLogger(__name__)


class ApprovalManager:
    """
    Lifecycle façade for an ApprovalRequest.

    Encapsulates the common transitions: create → validate → wait →
    approve / reject → archive, with snapshotting + audit along the way.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.lifecycle = ApprovalLifecycleManager(db)
        self.repository = ApprovalRepository(db)
        self.versions = ApprovalVersionManager(db)
        self.audit = ApprovalAuditService(db)

    async def approve(
        self,
        request_id: str,
        *,
        changed_by: str,
        reason: Optional[str] = None,
    ) -> Any:
        req = await self.lifecycle.transition(
            request_id,
            ApprovalState.APPROVED,
            changed_by=changed_by,
            reason=reason,
        )
        await self.audit.record(req, event_type="APPROVED", actor_id=changed_by, actor_role="HUMAN")
        return req

    async def reject(
        self,
        request_id: str,
        *,
        changed_by: str,
        reason: Optional[str] = None,
    ) -> Any:
        req = await self.lifecycle.transition(
            request_id,
            ApprovalState.REJECTED,
            changed_by=changed_by,
            reason=reason,
        )
        await self.audit.record(req, event_type="REJECTED", actor_id=changed_by, actor_role="HUMAN")
        return req

    async def cancel(
        self,
        request_id: str,
        *,
        changed_by: str,
        reason: Optional[str] = None,
    ) -> Any:
        req = await self.lifecycle.transition(
            request_id,
            ApprovalState.CANCELLED,
            changed_by=changed_by,
            reason=reason,
        )
        await self.audit.record(req, event_type="CANCELLED", actor_id=changed_by, actor_role="HUMAN")
        return req

    async def expire(self, request_id: str, *, changed_by: str = "system") -> Any:
        req = await self.lifecycle.transition(
            request_id,
            ApprovalState.EXPIRED,
            changed_by=changed_by,
            reason="TTL elapsed",
        )
        await self.audit.record(req, event_type="EXPIRED", actor_id=changed_by, actor_role="SYSTEM")
        return req

    async def archive(
        self,
        request_id: str,
        *,
        changed_by: str,
        reason: Optional[str] = None,
    ) -> Any:
        req = await self.lifecycle.transition(
            request_id,
            ApprovalState.ARCHIVED,
            changed_by=changed_by,
            reason=reason,
        )
        await self.audit.record(req, event_type="ARCHIVED", actor_id=changed_by, actor_role="HUMAN")
        return req


__all__ = ["ApprovalManager"]