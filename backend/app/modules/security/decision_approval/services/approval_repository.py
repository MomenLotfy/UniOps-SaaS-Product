"""
Approval Repository.

Persistence boundary for `ApprovalRequest`, `ApprovalPolicy`, and
`ApprovalEvaluationResult`.  Mirrors `DecisionStrategyRepository`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ApprovalState, ApprovalType
from ..models.approval import (
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalStatistics,
)
from .approval_interfaces import ApprovalEvaluationResult

logger = logging.getLogger(__name__)


class ApprovalRepository:
    """SQLAlchemy-backed persistence for the Approval Engine."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── ApprovalRequest CRUD ────────────────────────────────────────
    async def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        result = await self.db.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def list_requests(
        self,
        tenant_id: str,
        *,
        state: Optional[ApprovalState] = None,
        approval_type: Optional[ApprovalType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ApprovalRequest]:
        stmt = select(ApprovalRequest).where(ApprovalRequest.tenant_id == tenant_id)
        if state is not None:
            stmt = stmt.where(ApprovalRequest.approval_state == state)
        if approval_type is not None:
            stmt = stmt.where(ApprovalRequest.approval_type == approval_type)
        stmt = stmt.order_by(ApprovalRequest.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── ApprovalPolicy CRUD ─────────────────────────────────────────
    async def get_policy(self, policy_id: str) -> Optional[ApprovalPolicy]:
        result = await self.db.execute(
            select(ApprovalPolicy).where(ApprovalPolicy.id == policy_id)
        )
        return result.scalar_one_or_none()

    async def list_policies(self, tenant_id: Optional[str] = None) -> List[ApprovalPolicy]:
        stmt = select(ApprovalPolicy).order_by(ApprovalPolicy.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(ApprovalPolicy.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def save_policy(self, policy: ApprovalPolicy) -> ApprovalPolicy:
        self.db.add(policy)
        await self.db.flush()
        return policy

    # ── Aggregations ────────────────────────────────────────────────
    async def get_statistics(self, tenant_id: str) -> Dict[str, Any]:
        """Lightweight aggregate query — used by the engine for cache lookups."""
        try:
            stmt = select(
                ApprovalRequest.approval_type,
                ApprovalRequest.approval_state,
                func.count(ApprovalRequest.id),
            ).where(
                ApprovalRequest.tenant_id == tenant_id,
            ).group_by(
                ApprovalRequest.approval_type,
                ApprovalRequest.approval_state,
            )
            result = await self.db.execute(stmt)
            rows = result.all()
            return {
                "by_type_state": [
                    {"type": r[0].value if hasattr(r[0], "value") else r[0],
                     "state": r[1].value if hasattr(r[1], "value") else r[1],
                     "count": int(r[2])}
                    for r in rows
                ],
                "tenant_id": tenant_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:  # pragma: no cover - read-only, non-fatal
            logger.exception("approval statistics failed (non-fatal)")
            return {"by_type_state": [], "tenant_id": tenant_id}

    async def save_evaluation(self, result: ApprovalEvaluationResult) -> ApprovalStatistics:
        """Record one evaluation run."""
        approval_type = (
            result.candidate.approval_type if result.candidate else ApprovalType.AUTOMATIC
        )
        # R27: ApprovalStatistics inherits DecisionBase → correlation_id NOT NULL.
        effective_corr = (
            getattr(result.candidate, "correlation_id", None)
            or f"approval-evaluation:{result.tenant_id}:{result.decision_id}"
        )
        row = ApprovalStatistics(
            tenant_id=result.tenant_id,
            correlation_id=effective_corr,
            approval_type=approval_type,
            approval_state=ApprovalState.CREATED,  # always reflects pre-decision state
            count=1,
            avg_duration_ms=float(result.evaluation_duration_ms),
            avg_chain_length=float(len(result.candidate.requirements)) if result.candidate else 0.0,
            automatic_count=1 if (result.candidate and (result.candidate.auto_approve or result.candidate.auto_reject)) else 0,
            manual_count=0 if (result.candidate and (result.candidate.auto_approve or result.candidate.auto_reject)) else 1,
        )
        self.db.add(row)
        await self.db.flush()
        return row


__all__ = ["ApprovalRepository"]
