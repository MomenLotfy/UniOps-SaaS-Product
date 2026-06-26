from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.services.intelligence.sync.coordinator import SyncCoordinator, SyncState
from app.services.intelligence.sync.strategies import ProviderSyncStrategy, FullSyncEngine, IncrementalSyncEngine
from app.utils.logger import logger

class SyncManager:
    """
    Orchestrates the end-to-end synchronization process.
    """
    def __init__(self, db_session: Any):
        self.db = db_session
        self.coordinator = SyncCoordinator()
        self.strategies: Dict[str, ProviderSyncStrategy] = {
            "nvd": FullSyncEngine(), # Mock assignment
            "osv": IncrementalSyncEngine(), # Mock assignment
        }

    async def create_job(self, provider_id: str, sync_type: str) -> str:
        """
        Creates a new synchronization job in the system.
        """
        job_id = f"sync_{provider_id}_{int(datetime.utcnow().timestamp())}"
        # In real impl: save to SyncJob table
        await self.coordinator.transition(job_id, SyncState.CREATED, self.db)
        return job_id

    async def run_job(self, job_id: str) -> bool:
        """
        Executes a synchronization job through its full lifecycle.
        """
        logger.info(f"[SyncManager] Executing job {job_id}")

        # 1. State: Preparing
        await self.coordinator.transition(job_id, SyncState.PREPARING, self.db)

        # 2. State: Synchronizing
        await self.coordinator.transition(job_id, SyncState.SYNCHRONIZING, self.db)
        # Get strategy for the provider
        provider_id = "nvd" # Mock lookup
        strategy = self.strategies.get(provider_id, FullSyncEngine())
        raw_data = await strategy.execute_sync(job_id, {})

        # 3. State: Normalizing & Merging
        # Here we would call the NormalizationEngine and MergeEngine
        await self.coordinator.transition(job_id, SyncState.NORMALIZING, self.db)
        await self.coordinator.transition(job_id, SyncState.MERGING, self.db)

        # 4. State: Caching
        await self.coordinator.transition(job_id, SyncState.CACHING, self.db)

        # 5. Complete
        await self.coordinator.transition(job_id, SyncState.COMPLETED, self.db)
        return True
