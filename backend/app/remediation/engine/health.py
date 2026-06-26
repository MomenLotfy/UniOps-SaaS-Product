from __future__ import annotations
from typing import Dict, Any
from app.remediation.registry.registry import CapabilityRegistry
from app.remediation.events.bus import event_bus
from app.remediation.config import remediation_settings
from app.utils.logger import logger

class RemediationHealthChecker:
    """
    Performs health and readiness checks for the Remediation Engine components.
    """
    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    async def check_health(self) -> Dict[str, Any]:
        """
        Aggregates health status for all core components.
        """
        health_status = {
            "status": "healthy",
            "components": {}
        }

        # 1. Registry Health
        registry_health = await self._check_registry()
        health_status["components"]["registry"] = registry_health
        if registry_health["status"] != "healthy":
            health_status["status"] = "degraded"

        # 2. Event Bus Health
        bus_health = await self._check_event_bus()
        health_status["components"]["event_bus"] = bus_health
        if bus_health["status"] != "healthy":
            health_status["status"] = "degraded"

        # 3. Version Metadata
        health_status["metadata"] = {
            "engine_version": remediation_settings.engine_version,
            "event_bus_provider": remediation_settings.event_bus_provider,
            "lock_provider": remediation_settings.lock_provider
        }

        return health_status

    async def _check_registry(self) -> Dict[str, Any]:
        """Checks if the capability registry is initialized and has plugins."""
        plugins = self.registry.list_plugins()
        if not plugins:
            return {"status": "degraded", "reason": "No plugins registered"}

        return {
            "status": "healthy",
            "plugin_count": len(plugins),
            "plugins": [p.name for p in plugins],
            "capabilities_count": len(self.registry.list_all_capabilities())
        }

    async def _check_event_bus(self) -> Dict[str, Any]:
        """Checks if the event bus is responsive."""
        try:
            from app.remediation.events.bus import event_bus

            provider_name = remediation_settings.event_bus_provider

            # Basic operational check
            if event_bus is None or event_bus.provider is None:
                return {"status": "unhealthy", "reason": "Event bus not initialized"}

            # In a real distributed implementation, this would call a health check on the provider
            return {
                "status": "healthy",
                "provider": provider_name,
                "operational": True
            }
        except Exception as e:
            return {"status": "unhealthy", "reason": str(e)}
