from __future__ import annotations
from typing import Dict, List, Optional, Type
from app.services.intelligence.providers.base import IIntelligenceProvider
from app.utils.logger import logger

class IntelligenceProviderRegistry:
    """
    Singleton registry for managing intelligence providers.
    Handles registration, discovery, and lifecycle of providers.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IntelligenceProviderRegistry, cls).__new__(cls)
            cls._instance._providers: Dict[str, IIntelligenceProvider] = {}
        return cls._instance

    def register_provider(self, provider: IIntelligenceProvider) -> None:
        """Registers a provider instance."""
        self._providers[provider.provider_id] = provider
        logger.info(f"[IntelligenceRegistry] Registered provider: {provider.name} ({provider.provider_id})")

    def get_provider(self, provider_id: str) -> Optional[IIntelligenceProvider]:
        """Retrieves a specific provider by ID."""
        return self._providers.get(provider_id)

    def list_providers(self) -> List[IIntelligenceProvider]:
        """Returns all currently registered providers."""
        return list(self._providers.values())

    def get_all_provider_ids(self) -> List[str]:
        """Returns a list of registered provider IDs."""
        return list(self._providers.keys())
