from __future__ import annotations
from typing import List, Callable, Awaitable
from app.services.risk.context import RiskContext
from app.utils.logger import logger

class RiskEvaluationPipeline:
    """
    Modular pipeline for calculating a finding's risk.
    """
    def __init__(self):
        self.stages: List[Callable[[RiskContext], Awaitable[None]]] = []

    def add_stage(self, stage: Callable[[RiskContext], Awaitable[None]]) -> 'RiskEvaluationPipeline':
        self.stages.append(stage)
        return self

    async def execute(self, context: RiskContext) -> None:
        for stage in self.stages:
            try:
                await stage(context)
            except Exception as e:
                logger.error(f"[RiskPipeline] Stage failed: {e}")
