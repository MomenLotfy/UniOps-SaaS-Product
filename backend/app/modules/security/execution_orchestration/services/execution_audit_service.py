"""
Execution Audit Service.

Append-only ledger writer.  One row per significant event on an
`ExecutionPackage`.  Mirrors `decision_approval/services/
approval_audit_service.py`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.execution import ExecutionAudit, ExecutionPackage

logger = logging.getLogger(__name__)


class ExecutionAuditService:
    """Append-only audit ledger writer."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(
        self,
        package: ExecutionPackage,
        *,
        event_type: str,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ExecutionAudit:
        row = ExecutionAudit(
            tenant_id=package.tenant_id,
            package_id=package.id,
            event_type=(event_type or "UNKNOWN")[:100],
            actor_id=(actor_id or "system")[:100] if actor_id is not None else None,
            actor_role=(actor_role or "SYSTEM")[:100] if actor_role is not None else None,
            details=details,
            occurred_at=datetime.now(timezone.utc),
            correlation_id=package.correlation_id,
            trace_id=package.trace_id,
        )
        self.db.add(row)
        await self.db.flush()
        logger.debug(
            "execution audit tenant=%s package=%s event=%s actor=%s",
            package.tenant_id, package.id, event_type, actor_id,
        )
        return row


__all__ = ["ExecutionAuditService"]