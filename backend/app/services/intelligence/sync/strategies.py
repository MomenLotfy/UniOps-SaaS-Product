from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from app.utils.logger import logger

class ProviderSyncStrategy(ABC):
    """
    Defines how a specific provider's data is synchronized.
    """
    @property
    def provider_id(self) -> str:
        pass

    async def supports_full_sync(self) -> bool: return True
    async def supports_incremental_sync(self) -> bool: return False
    async def supports_delta_sync(self) -> bool: return False
    async def supports_checkpoints(self) -> bool: return False

    @abstractmethod
    async def execute_sync(self, job_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetches raw data from the provider.
        Returns a list of raw items to be normalized.
        """
        pass

class FullSyncEngine(ProviderSyncStrategy):
    """
    Implements a complete dump-and-load synchronization.
    """
    async def execute_sync(self, job_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[FullSyncEngine] Performing full sync for job {job_id}")
        # Architecture stub: returns an empty list
        return []

class IncrementalSyncEngine(ProviderSyncStrategy):
    """
    Implements synchronization based on a checkpoint or timestamp.
    """
    async def execute_sync(self, job_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[IncrementalSyncEngine] Performing incremental sync for job {job_id}")
        # Architecture stub: returns an empty list
        return []
