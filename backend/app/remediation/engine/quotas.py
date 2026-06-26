from __future__ import annotations
from typing import Dict, Any, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.remediation.models.models import RemediationPlan
from app.remediation.config import remediation_settings
from app.remediation.exceptions import LockAcquisitionError # Assuming we'd add this to a generic error set

class ExecutionQuotas:
    """
    Enforces tenant-level and global execution limits to prevent resource exhaustion.
    """
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def check_quota(self, tenant_id: str) -> bool:
        """
        Validates if the tenant has exceeded their concurrent execution quota.
        """
        # 1. Check Global Limit
        global_count = await self._get_active_execution_count(None)
        if global_count >= remediation_settings.max_global_executions:
            return False

        # 2. Check Tenant Limit
        tenant_count = await self._get_active_execution_count(tenant_id)
        if tenant_count >= remediation_settings.max_concurrent_executions_per_tenant:
            return False

        return True

    async def _get_active_execution_count(self, tenant_id: Optional[str]) -> int:
        """
        Counts plans currently in a non-terminal state.
        """
        # States that are considered "active"
        active_states = ["PLANNING", "WAITING_FOR_CAPABILITY", "READY_FOR_EXECUTION", "EXECUTING"]

        query = select(func.count(RemediationPlan.id)).where(
            RemediationPlan.status.in_(active_states)
        )

        if tenant_id:
            query = query.where(RemediationPlan.tenant_id == tenant_id)

        result = await self.db.execute(query)
        return result.scalar() or 0
