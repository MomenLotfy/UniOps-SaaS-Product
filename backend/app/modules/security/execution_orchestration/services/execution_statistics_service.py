"""
Execution Statistics Service.

Per-tenant metrics.  One `ExecutionStatistics` row per pipeline run,
broken out by `package_state`.  Mirrors `decision_approval/services/
approval_statistics_service.py`.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ExecutionPackageState
from ..models.execution import ExecutionPackage, ExecutionStatistics

logger = logging.getLogger(__name__)


class ExecutionStatisticsService:
    """Append-only metrics writer."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(
        self,
        package: ExecutionPackage,
        *,
        duration_ms: float,
        size_kb: float,
        rejected: bool,
        ready: bool,
    ) -> ExecutionStatistics:
        row = ExecutionStatistics(
            tenant_id=package.tenant_id,
            package_state=package.package_state,
            count=1,
            avg_duration_ms=float(duration_ms),
            avg_package_size_kb=float(size_kb),
            rejected_count=1 if rejected else 0,
            ready_count=1 if ready else 0,
            package_id=package.id,
            correlation_id=package.correlation_id,
            trace_id=package.trace_id,
        )
        self.db.add(row)
        await self.db.flush()
        logger.debug(
            "execution stats recorded tenant=%s state=%s duration=%.1fms size=%.2fkb",
            package.tenant_id, package.package_state, duration_ms, size_kb,
        )
        return row


__all__ = ["ExecutionStatisticsService"]