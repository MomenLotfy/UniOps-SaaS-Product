"""
Approval Audit Service.

Append-only audit ledger entries — one row per significant event.
Mirrors the audit patterns used elsewhere in the security module.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.approval import ApprovalAudit, ApprovalRequest

logger = logging.getLogger(__name__)


class ApprovalAuditService:
    """Writes ApprovalAudit rows.  Append-only."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(
        self,
        request: ApprovalRequest,
        *,
        event_type: str,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ApprovalAudit:
        row = ApprovalAudit(
            tenant_id=request.tenant_id,
            request_id=request.id,
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            details=details or {},
            occurred_at=datetime.now(timezone.utc).isoformat(),
            correlation_id=request.correlation_id,
            trace_id=request.trace_id,
        )
        self.db.add(row)
        await self.db.flush()
        logger.debug(
            "approval audit request=%s event=%s actor=%s",
            request.id, event_type, actor_id,
        )
        return row


__all__ = ["ApprovalAuditService"]
