from __future__ import annotations
from typing import List, Optional
from app.services.intelligence.providers.base import IIntelligenceProvider
from app.services.intelligence.providers.registry import IntelligenceProviderRegistry
from app.utils.logger import logger

class ProviderCapabilityResolver:
    """
    Logic to select the 'best' provider for a given intelligence request
    based on priority, confidence, and capability.
    """
    def __init__(self, registry: IntelligenceProviderRegistry):
        self.registry = registry

    async def resolve_best_provider(self, lookup_type: str, context: Optional[dict] = None) -> Optional[IIntelligenceProvider]:
        """
        Resolves the optimal provider for a specific lookup type.
        Currently uses a simple priority-based selection from active providers.
        """
        providers = self.registry.discover_capabilities(lookup_type)
        if not providers:
            logger.warning(f"[CapabilityResolver] No active providers found supporting {lookup_type}")
            return None

        # In a full implementation, this would query ProviderConfiguration.priority
        # and potentially consider the context (e.g. target package) to weight results.
        # For now, we return the first available capable provider.
        return providers[0]

    async def resolve_all_capable_providers(self, lookup_type: str) -> List[IIntelligenceProvider]:
        """
        Returns all active providers that can handle the requested lookup type.
        """
        return self.registry.discover_capabilities(lookup_type)
