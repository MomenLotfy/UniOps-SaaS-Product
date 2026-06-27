"""
Approval Lifecycle Manager.

Transitions ApprovalState with deterministic validity checks.  Mirrors
`DecisionStrategyLifecycleManager`.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import (
    ApprovalState,
    TERMINAL_APPROVAL_STATES,
    VALID_APPROVAL_TRANSITIONS,
)
from ..models.approval import ApprovalHistory, ApprovalRequest
from .approval_interfaces import IApprovalLifecycleManager

logger = logging.getLogger(__name__)


class ApprovalLifecycleManager(IApprovalLifecycleManager):
    """Validates + records every state change."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def can_transition(self, from_state: ApprovalState, to_state: ApprovalState) -> bool:
        allowed = VALID_APPROVAL_TRANSITIONS.get(from_state, [])
        return to_state in allowed

    async def transition(
        self,
        request_id: str,
        to_state: ApprovalState,
        *,
        changed_by: str,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """Apply the transition + append a history row.  Raises on illegal moves."""
        if to_state in TERMINAL_APPROVAL_STATES and to_state != ApprovalState.ARCHIVED:
            # ARCHIVED is the only allowed terminal here.
            pass

        result = await self.db.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == request_id)
        )
        req: Optional[ApprovalRequest] = result.scalar_one_or_none()
        if req is None:
            raise ValueError(f"ApprovalRequest {request_id} not found")

        from_state = req.approval_state
        if not self.can_transition(from_state, to_state):
            raise ValueError(
                f"Illegal transition {from_state} -> {to_state} for ApprovalRequest {request_id}"
            )

        req.approval_state = to_state
        req.version = (req.version or 1) + 1
        await self.db.flush()

        history = ApprovalHistory(
            tenant_id=req.tenant_id,
            request_id=req.id,
            from_state=from_state,
            to_state=to_state,
            changed_by=changed_by,
            change_reason=reason,
            correlation_id=req.correlation_id,
            trace_id=req.trace_id,
        )
        self.db.add(history)
        await self.db.flush()
        logger.info(
            "approval transition request=%s %s -> %s by=%s",
            request_id, from_state, to_state, changed_by,
        )
        return req


__all__ = ["ApprovalLifecycleManager"]
