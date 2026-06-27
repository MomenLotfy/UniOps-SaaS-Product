"""
Execution Version Manager.

Captures versioned snapshots of an `ExecutionPackage`.  Each
`ExecutionVersion` row is immutable; rollback reads the latest
matching version.

Mirrors `decision_approval/services/approval_version_manager.py`.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.execution import ExecutionPackage, ExecutionVersion
from .execution_package_serializer import serialize_candidate

logger = logging.getLogger(__name__)


class ExecutionVersionManager:
    """Persists ExecutionVersion snapshots; nothing else."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def snapshot(
        self,
        package: ExecutionPackage,
        *,
        change_summary: str = "",
        candidate_payload: Dict[str, Any] = None,
    ) -> ExecutionVersion:
        version_number = await self._next_version_number(package.id)
        snapshot = candidate_payload if candidate_payload is not None else self._snapshot_from_package(package)
        row = ExecutionVersion(
            tenant_id=package.tenant_id,
            package_id=package.id,
            version_number=version_number,
            snapshot=snapshot,
            change_summary=(change_summary or "")[:2000] or None,
            correlation_id=package.correlation_id,
            trace_id=package.trace_id,
        )
        self.db.add(row)
        await self.db.flush()
        logger.info(
            "execution version snap package=%s v=%d",
            package.id, version_number,
        )
        return row

    async def list_versions(self, package_id: str) -> List[ExecutionVersion]:
        stmt = (
            select(ExecutionVersion)
            .where(ExecutionVersion.package_id == package_id)
            .order_by(ExecutionVersion.version_number.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def latest(self, package_id: str) -> ExecutionVersion:
        stmt = (
            select(ExecutionVersion)
            .where(ExecutionVersion.package_id == package_id)
            .order_by(ExecutionVersion.version_number.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    # ── helpers ───────────────────────────────────────────────────
    async def _next_version_number(self, package_id: str) -> int:
        stmt = (
            select(ExecutionVersion.version_number)
            .where(ExecutionVersion.package_id == package_id)
            .order_by(ExecutionVersion.version_number.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        latest = result.scalar_one_or_none()
        return int(latest or 0) + 1

    @staticmethod
    def _snapshot_from_package(package: ExecutionPackage) -> Dict[str, Any]:
        """Lightweight snapshot built from the package row itself."""
        return {
            "package_id":     package.id,
            "package_state":  package.package_state.value if hasattr(package.package_state, "value") else str(package.package_state),
            "package_version": package.package_version,
            "decision_id":    package.decision_id,
            "strategy_id":    package.strategy_id,
            "approval_id":    package.approval_id,
            "summary":        package.summary,
            "payload_hash":   package.payload_hash,
            "dependency_count": package.dependency_count,
            "constraint_count": package.constraint_count,
            "metadata_count":   package.metadata_count,
            "package_size_kb":  package.package_size_kb,
        }


__all__ = ["ExecutionVersionManager"]