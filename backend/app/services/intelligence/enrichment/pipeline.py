from __future__ import annotations
from typing import Any, List, Callable, Awaitable
from app.utils.logger import logger
from app.services.intelligence.enrichment.context import EnrichmentContext

class EnrichmentPipeline:
    """
    Modular pipeline that executes a sequence of enrichers.
    """
    def __init__(self):
        self.stages: List[Callable[[EnrichmentContext], Awaitable[None]]] = []

    def add_stage(self, enricher: Callable[[EnrichmentContext], Awaitable[None]]) -> 'EnrichmentPipeline':
        self.stages.append(enricher)
        return self

    async def execute(self, context: EnrichmentContext) -> None:
        for stage in self.stages:
            try:
                # Handle both IEnricher instances and raw callables
                if hasattr(stage, 'enrich'):
                    await stage.enrich(context)
                else:
                    await stage(context)
            except Exception as e:
                logger.error(f"[EnrichmentPipeline] Stage failed: {e}")
                # We continue the pipeline even if one enricher fails (best effort)
