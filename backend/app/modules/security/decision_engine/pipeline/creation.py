"""
Sprint 1 R1: DecisionEngine must be instantiated with the AsyncSession
that BasePipelineStage already exposes via `self.db`.

Sprint 1 R3+R4: DecisionEngine.determine_decision now takes the
existing persisted Decision aggregate as its first argument and
returns the SAME aggregate (mutated) plus plans/reasons/resolution.
The stage below is only meaningful when ``context`` carries a
``decision`` reference — pipeline/creation.py is a thin shim that
delegates to DecisionEngine and never creates a fresh Decision.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DecisionInvariantError
from ..services.decision_engine import DecisionEngine
from .base import BasePipelineStage


class DecisionCreationStage(BasePipelineStage):
    """
    Stage 5: Core deterministic logic to mutate the existing
    decision aggregate.  Never creates a new Decision row.
    """

    async def execute(self, context, **kwargs):
        engine = DecisionEngine(self.db)
        # ``context.decision`` is the aggregate created by the
        # DecisionManager and flushed before this stage runs.
        decision = getattr(context, "decision", None)
        if decision is None or not getattr(decision, "id", None):
            raise DecisionInvariantError(
                "DecisionCreationStage requires a persisted Decision on the context "
                "(context.decision.id is missing)."
            )

        decision_obj, plans, reasons, resolution = await engine.determine_decision(
            decision, context,
        )
        return {
            "decision": decision_obj,
            "plans": plans,
            "reasons": reasons,
            "resolution": resolution,
        }