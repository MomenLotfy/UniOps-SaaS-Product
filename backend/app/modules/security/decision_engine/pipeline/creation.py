from ..pipeline.base import BasePipelineStage
from ..services.decision_engine import DecisionEngine
from sqlalchemy.ext.asyncio import AsyncSession

class DecisionCreationStage(BasePipelineStage):
    """
    Stage 5: Core deterministic logic to create the decision.
    """
    async def execute(self, context, **kwargs):
        engine = DecisionEngine()
        decision, plans, reasons = await engine.determine_decision(context)
        return {"decision": decision, "plans": plans, "reasons": reasons}
