"""
Execution Repository.

SQLAlchemy persistence boundary for the Execution Orchestration
Engine.  Mirrors `decision_approval/services/approval_repository.py`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ExecutionPackageState
from ..models.execution import (
    ExecutionAudit,
    ExecutionConstraint,
    ExecutionDependency,
    ExecutionHistory,
    ExecutionMetadata,
    ExecutionPackage,
    ExecutionPreparation,
    ExecutionReadiness,
    ExecutionRequirement,
    ExecutionStatistics,
    ExecutionSummary,
    ExecutionVersion,
)
from .execution_interfaces import (
    ExecutionEvaluationResult,
    IExecutionRepository,
)

logger = logging.getLogger(__name__)


class ExecutionRepository(IExecutionRepository):
    """SQLAlchemy-backed persistence for the Execution Engine."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── ExecutionPackage CRUD ─────────────────────────────────────
    async def get_package(self, package_id: str) -> Optional[ExecutionPackage]:
        result = await self.db.execute(
            select(ExecutionPackage).where(ExecutionPackage.id == package_id)
        )
        return result.scalar_one_or_none()

    async def list_packages(
        self,
        tenant_id: str,
        *,
        state: Optional[ExecutionPackageState] = None,
        decision_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ExecutionPackage]:
        stmt = select(ExecutionPackage).where(ExecutionPackage.tenant_id == tenant_id)
        if state is not None:
            stmt = stmt.where(ExecutionPackage.package_state == state)
        if decision_id is not None:
            stmt = stmt.where(ExecutionPackage.decision_id == decision_id)
        stmt = (
            stmt.order_by(ExecutionPackage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def save_package(self, package: ExecutionPackage) -> ExecutionPackage:
        self.db.add(package)
        await self.db.flush()
        return package

    # ── History + Audit ───────────────────────────────────────────
    async def list_history(self, package_id: str) -> List[ExecutionHistory]:
        stmt = (
            select(ExecutionHistory)
            .where(ExecutionHistory.package_id == package_id)
            .order_by(ExecutionHistory.changed_at.asc(), ExecutionHistory.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_audit(self, package_id: str) -> List[ExecutionAudit]:
        stmt = (
            select(ExecutionAudit)
            .where(ExecutionAudit.package_id == package_id)
            .order_by(ExecutionAudit.occurred_at.asc(), ExecutionAudit.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Aggregations ──────────────────────────────────────────────
    async def get_statistics(self, tenant_id: str) -> Dict[str, Any]:
        """Lightweight aggregate query — used by the engine for cache lookups."""
        try:
            stmt = (
                select(
                    ExecutionPackage.package_state,
                    func.count(ExecutionPackage.id),
                    func.coalesce(func.avg(ExecutionPackage.package_size_kb), 0.0),
                )
                .where(ExecutionPackage.tenant_id == tenant_id)
                .group_by(ExecutionPackage.package_state)
            )
            result = await self.db.execute(stmt)
            rows = result.all()
            return {
                "by_state": [
                    {
                        "state": r[0].value if hasattr(r[0], "value") else str(r[0]),
                        "count": int(r[1]),
                        "avg_size_kb": float(r[2]),
                    }
                    for r in rows
                ],
                "tenant_id": tenant_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:  # pragma: no cover - read-only, non-fatal
            logger.exception("execution statistics failed (non-fatal)")
            return {"by_state": [], "tenant_id": tenant_id}


__all__ = ["ExecutionRepository"]