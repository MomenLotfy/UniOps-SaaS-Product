from __future__ import annotations
from typing import Dict, Any, Optional
from datetime import datetime
from app.services.intelligence.providers.base import IIntelligenceProvider
from app.services.intelligence.providers.registry import IntelligenceProviderRegistry
from app.utils.logger import logger

class ProviderHealthMonitor:
    """
    Monitors the health, latency, and availability of intelligence providers.
    """
    def __init__(self, registry: IntelligenceProviderRegistry):
        self.registry = registry
        self._health_stats: Dict[str, Dict[str, Any]] = {}

    async def perform_health_check(self, provider_id: str) -> Dict[str, Any]:
        """
        Triggers a health check for a specific provider and updates internal stats.
        """
        provider = self.registry.get_provider(provider_id)
        if not provider:
            return {"status": "unknown", "error": "Provider not registered"}

        try:
            result = await provider.check_health()
            # Ensure basic structure
            status = result.get("status", "unknown")
            latency = result.get("latency_ms", 0.0)

            self._health_stats[provider_id] = {
                "status": status,
                "latency_ms": latency,
                "last_check_at": datetime.utcnow().isoformat(),
                "error": result.get("error")
            }
            return self._health_stats[provider_id]
        except Exception as e:
            logger.error(f"[HealthMonitor] Health check failed for {provider_id}: {e}")
            status_info = {
                "status": "unhealthy",
                "latency_ms": None,
                "last_check_at": datetime.utcnow().isoformat(),
                "error": str(e)
            }
            self._health_stats[provider_id] = status_info
            return status_info

    async def get_all_health_statuses(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns the latest health snapshot for all registered providers.
        """
        # Trigger checks for any provider missing from current stats
        for pid in self.registry.get_all_provider_ids():
            if pid not in self._health_stats:
                await self.perform_health_check(pid)

        return self._health_stats
