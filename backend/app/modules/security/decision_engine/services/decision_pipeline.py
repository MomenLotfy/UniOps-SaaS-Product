from __future__ import annotations
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from .context_builder import DecisionContextBuilder
from .decision_validator import DecisionValidator
from .decision_engine import DecisionEngine
from .decision_manager import DecisionManager
from ..constants import DecisionPipelineStage, DecisionState

class DecisionPipeline:
    """
    Orchestrates the sequential stages of creating a security decision.
    """
    def __init__(
        self,
        db: AsyncSession,
        context_builder: DecisionContextBuilder,
        validator: DecisionValidator,
        engine: DecisionEngine,
        manager: DecisionManager
    ):
        self.db = db
        self.context_builder = context_builder
        self.validator = validator
        self.engine = engine
        self.manager = manager

    async def execute(self, tenant_id: str, finding_id: str, correlation_id: str):
        """
        Runs the full pipeline from Context Build to Statistics Update.
        """
        # Stage 1: Create Decision Entity
        decision = await self.manager.create_decision(tenant_id, correlation_id, "")
        # Note: context_id will be updated after build

        try:
            # Stage 2: Context Build
            await self.manager.transition_to(decision.id, DecisionState.CONTEXT_BUILDING)
            context = await self.context_builder.build_context(tenant_id, finding_id, correlation_id)
            self.db.add(context)
            await self.db.flush()
            decision.context_id = context.id

            # Stage 3: Validation
            await self.manager.transition_to(decision.id, DecisionState.VALIDATING)
            is_valid, error = await self.validator.validate_request(tenant_id, finding_id)
            if not is_valid:
                await self.manager.transition_to(decision.id, DecisionState.REJECTED, reason=error)
                return decision

            # Stage 4: Decision Creation (Powered by Rule Engine)
            decision_obj, plans, reasons = await self.engine.determine_decision(context)

            # Merge results into the original decision object
            decision.final_result = decision_obj.final_result
            await self.manager.transition_to(decision.id, DecisionState.READY)

            # Stage 5: Persistence
            self.db.add_all(plans + reasons)
            # Note: In real impl, would also add steps, evidence, etc.
            await self.db.commit()

        except Exception as e:
            await self.manager.transition_to(decision.id, DecisionState.REJECTED, reason=str(e))
            await self.db.rollback()
            raise e

        return decision
