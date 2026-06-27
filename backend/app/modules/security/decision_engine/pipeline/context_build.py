from ..pipeline.base import BasePipelineStage
from ..services.context_builder import DecisionContextBuilder
from sqlalchemy.ext.asyncio import AsyncSession

class ContextBuildStage(BasePipelineStage):
    """
    Stage 1: Aggregates la data from the platform into a DecisionContext.
    """
    async def execute(self, data: dict, **kwargs):
        tenant_id = data['tenant_id']
        finding_id = data['finding_id']
        correlation_id = data['correlation_id']

        builder = DecisionContextBuilder(self.db)
        context = await builder.build_context(tenant_id, finding_id, correlation_id)
        return context
