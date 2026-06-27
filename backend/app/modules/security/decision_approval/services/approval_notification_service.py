"""
Approval Notification Service — STUB ONLY.

Per the module specification, **notification delivery belongs to a
later module**.  This service persists a structured intent record so
that downstream notifiers (email, Slack, in-app, etc.) can be wired in
without touching the engine.  No external side effects are produced.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ApprovalActorRole
from ..models.approval import ApprovalRequest

logger = logging.getLogger(__name__)


class ApprovalNotificationService:
    """
    Records notification INTENT only.

    This service does NOT send emails, Slack messages, or any external
    notification.  A later module will consume the intent records.
    """

    def __init__(self, db: Optional[AsyncSession] = None) -> None:
        self.db = db
        self._pending: List[Dict[str, Any]] = []

    def build_intent(
        self,
        request: ApprovalRequest,
        *,
        event_type: str,
        recipients: List[ApprovalActorRole],
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        intent = {
            "request_id":    request.id,
            "tenant_id":     request.tenant_id,
            "event_type":    event_type,
            "recipients":    [r.value for r in recipients],
            "decision_id":   request.decision_id,
            "strategy_id":   request.strategy_id,
            "approval_state": request.approval_state.value if hasattr(request.approval_state, "value") else str(request.approval_state),
            "payload":       payload or {},
            "status":        "PENDING",
        }
        self._pending.append(intent)
        logger.debug(
            "approval notification intent request=%s event=%s recipients=%d",
            request.id, event_type, len(recipients),
        )
        return intent

    def drain_pending(self) -> List[Dict[str, Any]]:
        items = list(self._pending)
        self._pending.clear()
        return items


__all__ = ["ApprovalNotificationService"]
