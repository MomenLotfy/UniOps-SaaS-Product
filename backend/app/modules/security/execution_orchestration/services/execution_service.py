"""
Execution Service — read-only API façade.

Mirrors `decision_approval/services/approval_service.py`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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
from .execution_lifecycle_manager import ExecutionLifecycleManager
from .execution_repository import ExecutionRepository


class ExecutionService:
    """Read-only access to the Execution Orchestration Engine state."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = ExecutionRepository(db)
        self.lifecycle = ExecutionLifecycleManager(db)

    # ── Package queries ───────────────────────────────────────────
    async def get_package(self, package_id: str) -> Optional[ExecutionPackage]:
        return await self.repository.get_package(package_id)

    async def list_packages(
        self,
        tenant_id: str,
        *,
        state: Optional[ExecutionPackageState] = None,
        decision_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ExecutionPackage]:
        return await self.repository.list_packages(
            tenant_id,
            state=state,
            decision_id=decision_id,
            limit=limit,
            offset=offset,
        )

    # ── Detail queries ────────────────────────────────────────────
    async def get_preparation(self, package_id: str) -> Optional[ExecutionPreparation]:
        from sqlalchemy import select
        stmt = select(ExecutionPreparation).where(ExecutionPreparation.package_id == package_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_readiness(self, package_id: str) -> Optional[ExecutionReadiness]:
        from sqlalchemy import select
        stmt = select(ExecutionReadiness).where(ExecutionReadiness.package_id == package_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_dependencies(self, package_id: str) -> List[ExecutionDependency]:
        from sqlalchemy import select
        stmt = select(ExecutionDependency).where(ExecutionDependency.package_id == package_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_constraints(self, package_id: str) -> List[ExecutionConstraint]:
        from sqlalchemy import select
        stmt = select(ExecutionConstraint).where(ExecutionConstraint.package_id == package_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_requirements(self, package_id: str) -> List[ExecutionRequirement]:
        from sqlalchemy import select
        stmt = select(ExecutionRequirement).where(ExecutionRequirement.package_id == package_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_metadata(self, package_id: str) -> List[ExecutionMetadata]:
        from sqlalchemy import select
        stmt = select(ExecutionMetadata).where(ExecutionMetadata.package_id == package_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_history(self, package_id: str) -> List[ExecutionHistory]:
        return await self.repository.list_history(package_id)

    async def list_audit(self, package_id: str) -> List[ExecutionAudit]:
        return await self.repository.list_audit(package_id)

    async def list_versions(self, package_id: str) -> List[ExecutionVersion]:
        from sqlalchemy import select
        stmt = (
            select(ExecutionVersion)
            .where(ExecutionVersion.package_id == package_id)
            .order_by(ExecutionVersion.version_number.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_statistics(self, package_id: str) -> List[ExecutionStatistics]:
        from sqlalchemy import select
        stmt = select(ExecutionStatistics).where(ExecutionStatistics.package_id == package_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_summary(self, package_id: str) -> Optional[ExecutionSummary]:
        from sqlalchemy import select
        stmt = select(ExecutionSummary).where(ExecutionSummary.package_id == package_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ── Aggregations ──────────────────────────────────────────────
    async def get_statistics(self, tenant_id: str) -> Dict[str, Any]:
        return await self.repository.get_statistics(tenant_id)

    # ── Lifecycle (admin-only) ────────────────────────────────────
    async def archive_package(
        self, package_id: str, *, changed_by: str, reason: Optional[str] = None,
    ) -> ExecutionPackage:
        return await self.lifecycle.transition(
            package_id,
            ExecutionPackageState.ARCHIVED,
            changed_by=changed_by,
            reason=reason or "Manual archive",
        )


__all__ = ["ExecutionService"]
