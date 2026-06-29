from __future__ import annotations
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.services.base import BaseService
from ..models.decision import Decision
from ..services.decision_manager import DecisionManager
from ..services.decision_pipeline import DecisionPipeline
from ..services.context_builder import DecisionContextBuilder
from ..services.decision_validator import DecisionValidator
from ..services.decision_engine import DecisionEngine
from ..services.statistics_service import StatisticsService
from ..models.plan import DecisionPlan


class DecisionService(BaseService):
    """
    API Facade for the Decision Engine.

    Sprint 1 R6: detail/list queries eagerly load every relationship the
    API touches (``plan.steps``, ``reasons``, ``context``, ``policy_ref``)
    via ``selectinload`` so the route handlers can read them outside of
    the request transaction without triggering ``MissingGreenlet``.
    """

    # ── List ────────────────────────────────────────────────────────────
    async def list_decisions(
        self, tenant_id: str, status: Optional[str] = None
    ) -> List[Decision]:
        query = select(Decision).where(Decision.tenant_id == tenant_id)
        if status:
            query = query.where(Decision.status == status)
        # R6: pre-load the most-touched relationships on the list endpoint
        # so callers don't N+1 across the list render.
        query = query.options(
            selectinload(Decision.reasons),
            selectinload(Decision.plan).selectinload(DecisionPlan.steps),
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    # ── Detail ──────────────────────────────────────────────────────────
    async def get_decision_detail(
        self, tenant_id: str, decision_id: str
    ) -> Optional[Decision]:
        """
        R6: eagerly load every relationship the detail route reads.
        Without this, accessing ``decision.plan.steps`` etc. inside the
        route fires a synchronous lazy load in async context and raises
        ``MissingGreenlet``.
        """
        result = await self.db.execute(
            select(Decision)
            .where(Decision.id == decision_id, Decision.tenant_id == tenant_id)
            .options(
                selectinload(Decision.context),
                selectinload(Decision.reasons),
                selectinload(Decision.policy_ref),
                selectinload(Decision.history),
                selectinload(Decision.plan).selectinload(DecisionPlan.steps),
            )
        )
        return result.scalar_one_or_none()

    # ── Trigger ─────────────────────────────────────────────────────────
    async def request_decision(
        self, tenant_id: str, finding_id: str, correlation_id: str
    ) -> Decision:
        """
        Internal method to trigger the decision pipeline.

        Sprint 1 R1+R2: every collaborator is constructed with the real
        AsyncSession and DecisionPipeline now receives a real
        StatisticsService — no None placeholders, no missing args.
        """
        manager = DecisionManager(self.db)
        builder = DecisionContextBuilder(self.db)
        validator = DecisionValidator(self.db)
        engine = DecisionEngine(self.db)
        stats_service = StatisticsService(self.db)
        pipeline = DecisionPipeline(
            db=self.db,
            context_builder=builder,
            validator=validator,
            engine=engine,
            manager=manager,
            stats_service=stats_service,
        )

        return await pipeline.execute(tenant_id, finding_id, correlation_id)