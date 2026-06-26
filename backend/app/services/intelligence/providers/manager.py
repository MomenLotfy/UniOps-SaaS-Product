from __future__ import annotations
from typing import Dict, Any, List, Optional
from app.services.intelligence.providers.base import IIntelligenceProvider
from app.services.intelligence.providers.registry import IntelligenceProviderRegistry
from app.services.intelligence.providers.loader import ProviderLoader
from app.services.intelligence.providers.health_monitor import ProviderHealthMonitor
from app.services.intelligence.providers.capability_resolver import ProviderCapabilityResolver
from app.utils.logger import logger

class IntelligenceProviderManager:
    """
    The main facade for the Intelligence Provider system.
    Orchestrates the Registry, Loader, HealthMonitor, and CapabilityResolver.
    """
    def __init__(self):
        self.registry = IntelligenceProviderRegistry()
        self.loader = ProviderLoader()
        self.health_monitor = ProviderHealthMonitor(self.registry)
        self.capability_resolver = ProviderCapabilityResolver(self.registry)

    async def initialize_providers(self, provider_configs: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Initializes all configured providers.
        """
        if not provider_configs:
            logger.info("[ProviderManager] No provider configurations provided, skipping initialization.")
            return

        for config in provider_configs:
            pid = config.get("provider_id")
            if not pid:
                continue

            try:
                # Load instance
                provider = self.loader.load_provider(pid, config)
                # Register it (active status determined by config)
                self.registry.register_provider(
                    provider,
                    active=config.get("is_active", True)
                )
                logger.info(f"[ProviderManager] Successfully initialized provider {pid}")
            except Exception as e:
                logger.error(f"[ProviderManager] Failed to initialize provider {pid}: {e}")

    async def get_provider(self, provider_id: str) -> Optional[IIntelligenceProvider]:
        """Retrieves a specific provider instance."""
        return self.registry.get_provider(provider_id)

    async def resolve_provider(self, lookup_type: str, context: Optional[dict] = None) -> Optional[IIntelligenceProvider]:
        """Resolves the best provider for a specific lookup type."""
        return await self.capability_resolver.resolve_best_provider(lookup_type, context)

    async def get_health_report(self) -> Dict[str, Any]:
        """Returns a comprehensive health report of all providers."""
        return await self.health_monitor.get_all_health_statuses()

    async def list_active_providers(self) -> List[IIntelligenceProvider]:
        """Returns currently active providers."""
        return self.registry.list_providers(only_active=True)

    async def toggle_provider(self, provider_id: str, enabled: bool) -> bool:
        """Enables or disables a provider dynamically."""
        if enabled:
            return self.registry.enable_provider(provider_id)
        else:
            return self.registry.disable_provider(provider_id)
