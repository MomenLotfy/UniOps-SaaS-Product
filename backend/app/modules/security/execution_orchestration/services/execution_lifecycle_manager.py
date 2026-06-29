"""
Execution Lifecycle Manager.

Transitions `ExecutionPackageState` with deterministic validity checks.
Mirrors `decision_approval/services/approval_lifecycle_manager.py`.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ExecutionNotFoundError,
    IllegalExecutionTransitionError,
)
from ..constants import (
    ExecutionPackageState,
    VALID_EXECUTION_TRANSITIONS,
)
from ..models.execution import ExecutionHistory, ExecutionPackage
from .execution_interfaces import IExecutionLifecycleManager

logger = logging.getLogger(__name__)


class ExecutionLifecycleManager(IExecutionLifecycleManager):
    """Validates + records every state change for an ExecutionPackage."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def can_transition(
        self,
        from_state: ExecutionPackageState,
        to_state: ExecutionPackageState,
    ) -> bool:
        allowed = VALID_EXECUTION_TRANSITIONS.get(from_state, [])
        return to_state in allowed

    async def transition(
        self,
        tenant_id: str,
        package_id: str,
        to_state: ExecutionPackageState,
        *,
        changed_by: str,
        reason: Optional[str] = None,
    ) -> ExecutionPackage:
        """
        Apply the transition + append a history row.  Raises on illegal moves.

        Sprint 1 R8: ``tenant_id`` is now a required positional argument so
        the lookup is tenant-scoped — refuses to operate on a package that
        belongs to a different tenant.
        """
        result = await self.db.execute(
            select(ExecutionPackage).where(
                ExecutionPackage.id == package_id,
                ExecutionPackage.tenant_id == tenant_id,
            )
        )
        pkg: Optional[ExecutionPackage] = result.scalar_one_or_none()
        if pkg is None:
            raise ExecutionNotFoundError(f"{package_id} (tenant={tenant_id})")

        from_state = pkg.package_state
        if not self.can_transition(from_state, to_state):
            raise IllegalExecutionTransitionError(
                from_state=str(from_state.value if hasattr(from_state, "value") else from_state),
                to_state=str(to_state.value if hasattr(to_state, "value") else to_state),
            )

        pkg.package_state = to_state
        pkg.version = (pkg.version or 1) + 1
        await self.db.flush()

        history = ExecutionHistory(
            tenant_id=pkg.tenant_id,
            package_id=pkg.id,
            from_state=from_state,
            to_state=to_state,
            changed_by=changed_by,
            change_reason=reason,
            correlation_id=pkg.correlation_id,
            trace_id=pkg.trace_id,
        )
        self.db.add(history)
        await self.db.flush()
        logger.info(
            "execution transition package=%s %s -> %s by=%s",
            package_id, from_state, to_state, changed_by,
        )
        return pkg


__all__ = ["ExecutionLifecycleManager"]