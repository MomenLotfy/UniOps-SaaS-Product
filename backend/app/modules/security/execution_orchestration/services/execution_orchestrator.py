"""
Execution Orchestrator.

Public façade.  Wraps `ExecutionPipeline` and provides the high-level
methods that other modules (e.g. the future Remediation Engine) will
call.

Mirrors `ApprovalEngine` / `ApprovalService` from the approval module.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .execution_interfaces import ExecutionEvaluationResult
from .execution_pipeline import ExecutionPipeline

logger = logging.getLogger(__name__)


class ExecutionOrchestrator:
    """
    High-level entry point for the execution orchestration flow.

    Construction takes a DB session; every method opens its own
    `ExecutionPipeline` so callers don't need to know the internals.
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        pipeline: Optional[ExecutionPipeline] = None,
    ) -> None:
        self.db = db
        self.pipeline = pipeline or ExecutionPipeline(db)

    async def orchestrate(
        self,
        decision: Any,
        strategy: Any = None,
        approval: Any = None,
        *,
        tenant_id: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[List] = None,
        requirements: Optional[List] = None,
        summary: Optional[str] = None,
        actor_id: str = "system",
    ) -> ExecutionEvaluationResult:
        """
        Run the full pipeline.  Returns the `ExecutionEvaluationResult`;
        the caller is responsible for committing the surrounding
        transaction.
        """
        return await self.pipeline.run(
            decision=decision,
            strategy=strategy,
            approval=approval,
            tenant_id=tenant_id,
            raw_data=raw_data,
            metadata=metadata,
            requirements=requirements,
            summary=summary,
            actor_id=actor_id,
        )

    async def orchestrate_many(
        self,
        requests: List[Dict[str, Any]],
    ) -> List[ExecutionEvaluationResult]:
        """Convenience helper for bulk runs.  Same DB session for all."""
        out: List[ExecutionEvaluationResult] = []
        for req in requests:
            out.append(await self.orchestrate(**req))
        return out


__all__ = ["ExecutionOrchestrator"]