"""
Approval Version Manager.

Stores JSON snapshots of `ApprovalRequest` rows so that audit + rollback
queries are possible.  Mirrors the pattern used by `StrategyVersion`.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.approval import ApprovalRequest, ApprovalVersion

logger = logging.getLogger(__name__)


class ApprovalVersionManager:
    """Append-only version history for an ApprovalRequest."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def snapshot(
        self,
        request: ApprovalRequest,
        snapshot: Dict[str, Any],
        change_summary: Optional[str] = None,
    ) -> ApprovalVersion:
        version_number = (request.version or 1)
        row = ApprovalVersion(
            tenant_id=request.tenant_id,
            request_id=request.id,
            version_number=version_number,
            snapshot=snapshot,
            change_summary=change_summary,
            correlation_id=request.correlation_id,
            trace_id=request.trace_id,
        )
        self.db.add(row)
        await self.db.flush()
        logger.debug(
            "approval snapshot request=%s version=%s", request.id, version_number,
        )
        return row


__all__ = ["ApprovalVersionManager"]
