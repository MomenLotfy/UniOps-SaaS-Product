"""
Execution Service — read-only API façade.

Mirrors `decision_approval/services/approval_service.py`.

Sprint 1 R8: every per-package query now takes ``tenant_id`` and
applies it as a SQL WHERE clause in addition to the JWT-derived
tenant_id in the route layer.  Defense in depth — if a future
caller forgets the auth dependency, the service still refuses
to leak cross-tenant data.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
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
    async def get_package(
        self, tenant_id: str, package_id: str
    ) -> Optional[ExecutionPackage]:
        """R8: tenant-scoped lookup; refuses cross-tenant package_id."""
        return await self.repository.get_package(tenant_id, package_id)

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
    async def get_preparation(
        self, tenant_id: str, package_id: str
    ) -> Optional[ExecutionPreparation]:
        stmt = select(ExecutionPreparation).where(
            ExecutionPreparation.package_id == package_id,
            ExecutionPreparation.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_readiness(
        self, tenant_id: str, package_id: str
    ) -> Optional[ExecutionReadiness]:
        stmt = select(ExecutionReadiness).where(
            ExecutionReadiness.package_id == package_id,
            ExecutionReadiness.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_dependencies(
        self, tenant_id: str, package_id: str
    ) -> List[ExecutionDependency]:
        stmt = select(ExecutionDependency).where(
            ExecutionDependency.package_id == package_id,
            ExecutionDependency.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_constraints(
        self, tenant_id: str, package_id: str
    ) -> List[ExecutionConstraint]:
        stmt = select(ExecutionConstraint).where(
            ExecutionConstraint.package_id == package_id,
            ExecutionConstraint.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_requirements(
        self, tenant_id: str, package_id: str
    ) -> List[ExecutionRequirement]:
        stmt = select(ExecutionRequirement).where(
            ExecutionRequirement.package_id == package_id,
            ExecutionRequirement.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_metadata(
        self, tenant_id: str, package_id: str
    ) -> List[ExecutionMetadata]:
        stmt = select(ExecutionMetadata).where(
            ExecutionMetadata.package_id == package_id,
            ExecutionMetadata.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_history(
        self, tenant_id: str, package_id: str
    ) -> List[ExecutionHistory]:
        stmt = select(ExecutionHistory).where(
            ExecutionHistory.package_id == package_id,
            ExecutionHistory.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_audit(
        self, tenant_id: str, package_id: str
    ) -> List[ExecutionAudit]:
        stmt = select(ExecutionAudit).where(
            ExecutionAudit.package_id == package_id,
            ExecutionAudit.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_versions(
        self, tenant_id: str, package_id: str
    ) -> List[ExecutionVersion]:
        stmt = (
            select(ExecutionVersion)
            .where(
                ExecutionVersion.package_id == package_id,
                ExecutionVersion.tenant_id == tenant_id,
            )
            .order_by(ExecutionVersion.version_number.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_statistics(
        self, tenant_id: str, package_id: str
    ) -> List[ExecutionStatistics]:
        stmt = select(ExecutionStatistics).where(
            ExecutionStatistics.package_id == package_id,
            ExecutionStatistics.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_summary(
        self, tenant_id: str, package_id: str
    ) -> Optional[ExecutionSummary]:
        stmt = select(ExecutionSummary).where(
            ExecutionSummary.package_id == package_id,
            ExecutionSummary.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ── Aggregations ──────────────────────────────────────────────
    async def get_statistics(self, tenant_id: str) -> Dict[str, Any]:
        return await self.repository.get_statistics(tenant_id)

    # ── Lifecycle (admin-only) ────────────────────────────────────
    async def archive_package(
        self,
        tenant_id: str,
        package_id: str,
        *,
        changed_by: str,
        reason: Optional[str] = None,
    ) -> ExecutionPackage:
        """R8: tenant-scoped archive; admin-only via the calling route."""
        return await self.lifecycle.transition(
            tenant_id,
            package_id,
            ExecutionPackageState.ARCHIVED,
            changed_by=changed_by,
            reason=reason or "Manual archive",
        )


__all__ = ["ExecutionService"]