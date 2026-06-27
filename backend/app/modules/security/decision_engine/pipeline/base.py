from abc import ABC, abstractmethod
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

class BasePipelineStage(ABC):
    """
    Abstract base class for all Decision Engine pipeline stages.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    @abstractmethod
    async def execute(self, context: Any, **kwargs) -> Any:
        """
        Execute the stage logic.
        """
        pass
