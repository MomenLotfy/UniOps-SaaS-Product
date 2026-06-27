from ..pipeline.base import BasePipelineStage
from ..services.decision_validator import DecisionValidator
from sqlalchemy.ext.asyncio import AsyncSession

class ValidationStage(BasePipelineStage):
    """
    Stage 2: Verifies tenant isolation and asset existence.
    """
    async def execute(self, context, **kwargs):
        validator = DecisionValidator(self.db)
        is_valid, error = await validator.validate_request(
            context.tenant_id,
            context.source_finding_id
        )
        if not is_valid:
            raise ValueError(f"Validation failed: {error}")
        return context
