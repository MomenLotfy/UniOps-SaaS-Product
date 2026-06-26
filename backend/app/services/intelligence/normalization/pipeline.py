from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable, Awaitable
from app.utils.logger import logger

class NormalizationPipeline:
    """
    Modular pipeline for transforming raw provider data into canonical intelligence.
    Each stage is a callable that processes the data.
    """
    def __init__(self):
        self.stages: List[Callable[[Any], Awaitable[Any]]] = []

    def add_stage(self, stage: Callable[[Any], Awaitable[Any]]) -> 'NormalizationPipeline':
        self.stages.append(stage)
        return self

    async def execute(self, data: Any) -> Any:
        current_val = data
        for stage in self.stages:
            try:
                current_val = await stage(current_val)
                if current_val is None:
                    return None
            except Exception as e:
                logger.error(f"[NormalizationPipeline] Stage {stage.__name__} failed: {e}")
                raise e
        return current_val
