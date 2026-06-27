"""
Approval Service — read-only API facade.

Mirrors `DecisionStrategyService`.  All methods are READ-ONLY; the
router only exposes GET endpoints.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ApprovalState, ApprovalType
from ..models.approval import ApprovalRequest
from .approval_engine import ApprovalEngine
from .approval_pipeline import ApprovalEvaluationPipeline
from .approval_repository import ApprovalRepository
from .approval_audit_service import ApprovalAuditService
from .approval_lifecycle_manager import ApprovalLifecycleManager
from .approval_version_manager import ApprovalVersionManager
from .approval_serializer import serialize_candidate

logger = logging.getLogger(__name__)


class ApprovalService:
    """
    Read-only public API for the Approval Engine.

    Composition root holds the pipeline + repository + lifecycle +
    version + audit services.  Construct with an AsyncSession; share
    a single instance per request via FastAPI dependencies.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.engine = ApprovalEngine()
        self.pipeline = ApprovalEvaluationPipeline(db, engine=self.engine)
        self.repository = ApprovalRepository(db)
        self.lifecycle = ApprovalLifecycleManager(db)
        self.versions = ApprovalVersionManager(db)
        self.audit = ApprovalAuditService(db)

    # ── Read API ──────────────────────────────────────────────────
    async def list_requests(
        self,
        tenant_id: str,
        *,
        state: Optional[ApprovalState] = None,
        approval_type: Optional[ApprovalType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ApprovalRequest]:
        return await self.repository.list_requests(
            tenant_id,
            state=state,
            approval_type=approval_type,
            limit=limit,
            offset=offset,
        )

    async def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return await self.repository.get_request(request_id)

    async def get_statistics(self, tenant_id: str) -> Dict[str, Any]:
        return await self.repository.get_statistics(tenant_id)

    async def list_policies(self, tenant_id: Optional[str] = None) -> List[Any]:
        return await self.repository.list_policies(tenant_id=tenant_id)

    # ── Pipeline accessor (for write-side callers / internal use) ──
    def get_pipeline(self) -> ApprovalEvaluationPipeline:
        return self.pipeline

    def get_engine(self) -> ApprovalEngine:
        return self.engine

    # ── Helpers exposed for tests / pipelines ──────────────────────
    @staticmethod
    def serialize_candidate(candidate: Any) -> Dict[str, Any]:
        return serialize_candidate(candidate)


__all__ = ["ApprovalService"]