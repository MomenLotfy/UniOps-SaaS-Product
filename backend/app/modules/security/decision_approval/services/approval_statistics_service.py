"""
Approval Statistics Service.

Per-tenant aggregate metrics + per-event duration tracking.
Mirrors `DecisionStrategyStatisticsService`.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ApprovalState, ApprovalType
from ..models.approval import ApprovalRequest, ApprovalStatistics

logger = logging.getLogger(__name__)


class ApprovalStatisticsService:
    """Updates aggregate metrics for the Approval Engine."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_evaluation(
        self,
        *,
        tenant_id: str,
        approval_type: ApprovalType,
        duration_ms: int,
        chain_length: int,
        automatic: bool,
    ) -> None:
        try:
            row = ApprovalStatistics(
                tenant_id=tenant_id,
                approval_type=approval_type,
                approval_state=ApprovalState.CREATED,
                count=1,
                avg_duration_ms=float(duration_ms),
                avg_chain_length=float(chain_length),
                automatic_count=1 if automatic else 0,
                manual_count=0 if automatic else 1,
            )
            self.db.add(row)
            await self.db.flush()
        except Exception:  # pragma: no cover - non-fatal
            logger.exception("approval record_evaluation failed (non-fatal)")

    async def record_transition(
        self,
        *,
        tenant_id: str,
        approval_type: ApprovalType,
        to_state: ApprovalState,
        duration_ms: int,
        chain_length: int,
        automatic: bool,
    ) -> None:
        try:
            row = ApprovalStatistics(
                tenant_id=tenant_id,
                approval_type=approval_type,
                approval_state=to_state,
                count=1,
                avg_duration_ms=float(duration_ms),
                avg_chain_length=float(chain_length),
                automatic_count=1 if automatic else 0,
                manual_count=0 if automatic else 1,
            )
            self.db.add(row)
            await self.db.flush()
        except Exception:  # pragma: no cover - non-fatal
            logger.exception("approval record_transition failed (non-fatal)")

    async def record_rejection(
        self,
        *,
        tenant_id: str,
        approval_type: ApprovalType,
    ) -> None:
        try:
            row = ApprovalStatistics(
                tenant_id=tenant_id,
                approval_type=approval_type,
                approval_state=ApprovalState.REJECTED,
                count=1,
                avg_duration_ms=0.0,
                avg_chain_length=0.0,
                automatic_count=0,
                manual_count=1,
            )
            self.db.add(row)
            await self.db.flush()
        except Exception:  # pragma: no cover - non-fatal
            logger.exception("approval record_rejection failed (non-fatal)")

    async def record_expiration(
        self,
        *,
        tenant_id: str,
        approval_type: ApprovalType,
    ) -> None:
        try:
            row = ApprovalStatistics(
                tenant_id=tenant_id,
                approval_type=approval_type,
                approval_state=ApprovalState.EXPIRED,
                count=1,
                avg_duration_ms=0.0,
                avg_chain_length=0.0,
                automatic_count=0,
                manual_count=1,
            )
            self.db.add(row)
            await self.db.flush()
        except Exception:  # pragma: no cover - non-fatal
            logger.exception("approval record_expiration failed (non-fatal)")


__all__ = ["ApprovalStatisticsService"]
